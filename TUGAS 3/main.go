package main

import (
	"bufio"
	"context"
	"fmt"
	"log"
	"os"
	"os/signal"
	"sort"
	"strings"
	"syscall"

	"bazil.org/fuse"
	"bazil.org/fuse/fs"
)

// ---------- Data ----------

type Data struct {
	cols []string                     // imsyak, shubuh, ..., isya
	days map[string]map[string]string // "01" -> {"maghrib": "17:25", ...}
}

func loadData(path string) (*Data, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	d := &Data{days: make(map[string]map[string]string)}
	sc := bufio.NewScanner(f)
	first := true
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" {
			continue
		}
		fields := strings.Fields(line)
		if first {
			first = false
			// header: abaikan komentar setelah "<=", huruf kecil semua
			for _, h := range fields[1:] {
				if h == "<=" {
					break
				}
				d.cols = append(d.cols, strings.ToLower(h))
			}
			continue
		}
		if len(fields)-1 < len(d.cols) {
			continue // baris tidak lengkap
		}
		row := make(map[string]string)
		for i, c := range d.cols {
			row[c] = fields[i+1]
		}
		d.days[fields[0]] = row
	}
	if len(d.days) == 0 || len(d.cols) == 0 {
		return nil, fmt.Errorf("isi %s kosong atau format salah", path)
	}
	return d, sc.Err()
}

// ---------- Filesystem ----------

type FS struct{ data *Data }

func (f FS) Root() (fs.Node, error) { return &RootDir{f.data}, nil }

// Root: berisi direktori 01..31
type RootDir struct{ data *Data }

func (r *RootDir) Attr(ctx context.Context, a *fuse.Attr) error {
	a.Mode = os.ModeDir | 0555
	return nil
}

func (r *RootDir) Lookup(ctx context.Context, name string) (fs.Node, error) {
	if _, ok := r.data.days[name]; ok {
		return &DayDir{r.data, name}, nil
	}
	return nil, syscall.ENOENT
}

func (r *RootDir) ReadDirAll(ctx context.Context) ([]fuse.Dirent, error) {
	var names []string
	for k := range r.data.days {
		names = append(names, k)
	}
	sort.Strings(names)
	var out []fuse.Dirent
	for _, n := range names {
		out = append(out, fuse.Dirent{Name: n, Type: fuse.DT_Dir})
	}
	return out, nil
}

// Direktori tanggal: berisi file imsyak, shubuh, ..., isya
type DayDir struct {
	data *Data
	day  string
}

func (d *DayDir) Attr(ctx context.Context, a *fuse.Attr) error {
	a.Mode = os.ModeDir | 0555
	return nil
}

func (d *DayDir) Lookup(ctx context.Context, name string) (fs.Node, error) {
	if _, ok := d.data.days[d.day][name]; ok {
		return &TimeFile{d.data, d.day, name}, nil
	}
	return nil, syscall.ENOENT
}

func (d *DayDir) ReadDirAll(ctx context.Context) ([]fuse.Dirent, error) {
	var out []fuse.Dirent
	for _, c := range d.data.cols {
		out = append(out, fuse.Dirent{Name: c, Type: fuse.DT_File})
	}
	return out, nil
}

// File waktu sholat
type TimeFile struct {
	data *Data
	day  string
	name string
}

func (t *TimeFile) content() []byte {
	return []byte(fmt.Sprintf("tanggal %s %s -> %s\n", t.day, t.name, t.data.days[t.day][t.name]))
}

func (t *TimeFile) Attr(ctx context.Context, a *fuse.Attr) error {
	a.Mode = 0444
	a.Size = uint64(len(t.content()))
	return nil
}

func (t *TimeFile) ReadAll(ctx context.Context) ([]byte, error) {
	return t.content(), nil
}

// ---------- main ----------

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintf(os.Stderr, "pemakaian: %s <mountpoint> [file-data]\n", os.Args[0])
		os.Exit(2)
	}
	mountpoint := os.Args[1]
	dataFile := "waktu.txt"
	if len(os.Args) >= 3 {
		dataFile = os.Args[2]
	}

	data, err := loadData(dataFile)
	if err != nil {
		log.Fatal(err)
	}

	c, err := fuse.Mount(mountpoint,
		fuse.FSName("waktu"),
		fuse.Subtype("waktufs"),
		fuse.ReadOnly(),
	)
	if err != nil {
		log.Fatal(err)
	}
	defer c.Close()

	// Ctrl+C -> unmount rapi
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, os.Interrupt, syscall.SIGTERM)
	go func() {
		<-sig
		fuse.Unmount(mountpoint)
	}()

	if err := fs.Serve(c, FS{data}); err != nil {
		log.Fatal(err)
	}
}