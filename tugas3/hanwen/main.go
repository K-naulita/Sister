git add "tugas3"package main

import (
	"bufio"
	"context"
	"fmt"
	"log"
	"os"
	"os/signal"
	"strings"
	"syscall"

	"github.com/hanwen/go-fuse/v2/fs"
	"github.com/hanwen/go-fuse/v2/fuse"
)

type Data struct {
	cols []string
	days map[string]map[string]string
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
			for _, h := range fields[1:] {
				if h == "<=" {
					break
				}
				d.cols = append(d.cols, strings.ToLower(h))
			}
			continue
		}
		if len(fields)-1 < len(d.cols) {
			continue
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

type Root struct {
	fs.Inode
	data *Data
}

var _ = (fs.NodeOnAdder)((*Root)(nil))

func (r *Root) OnAdd(ctx context.Context) {
	for day, row := range r.data.days {
		dir := r.NewPersistentInode(ctx, &fs.Inode{},
			fs.StableAttr{Mode: syscall.S_IFDIR})
		for _, col := range r.data.cols {
			isi := fmt.Sprintf("tanggal %s %s -> %s\n", day, col, row[col])
			file := r.NewPersistentInode(ctx,
				&fs.MemRegularFile{
					Data: []byte(isi),
					Attr: fuse.Attr{Mode: 0444},
				},
				fs.StableAttr{Mode: syscall.S_IFREG})
			dir.AddChild(col, file, true)
		}
		r.AddChild(day, dir, true)
	}
}

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintf(os.Stderr, "pemakaian: %s <mountpoint> [file-data]\n",
			os.Args[0])
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

	server, err := fs.Mount(mountpoint, &Root{data: data}, &fs.Options{
		MountOptions: fuse.MountOptions{
			Name:    "waktufs",
			FsName:  "waktu",
			Options: []string{"ro"}, // read-only
		},
	})
	if err != nil {
		log.Fatal(err)
	}

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, os.Interrupt, syscall.SIGTERM)
	go func() {
		<-sig
		server.Unmount()
	}()

	server.Wait()
}