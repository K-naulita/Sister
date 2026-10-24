package main

import (
	"fmt"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"

	"go.nanomsg.org/mangos/v3"
	"go.nanomsg.org/mangos/v3/protocol/rep"
	"go.nanomsg.org/mangos/v3/protocol/req"
	_ "go.nanomsg.org/mangos/v3/transport/tcp"
)

const (
	total    = 8
	basePort = 9000
)

var (
	id          int
	mu          sync.Mutex
	electing    bool
	coordinator = -1
)

func addr(n int) string {
	return fmt.Sprintf("tcp://127.0.0.1:%d", basePort+n)
}

func logf(format string, a ...interface{}) {
	fmt.Printf("[node %d] %s\n", id, fmt.Sprintf(format, a...))
}

func send(to int, msg string) (string, bool) {
	s, err := req.NewSocket()
	if err != nil {
		return "", false
	}
	defer s.Close()
	s.SetOption(mangos.OptionSendDeadline, 500*time.Millisecond)
	s.SetOption(mangos.OptionRecvDeadline, 500*time.Millisecond)
	if err := s.Dial(addr(to)); err != nil {
		return "", false
	}
	if err := s.Send([]byte(msg)); err != nil {
		return "", false
	}
	b, err := s.Recv()
	if err != nil {
		return "", false
	}
	return string(b), true
}

func startElection() {
	mu.Lock()
	if electing || coordinator == id {
		mu.Unlock()
		return
	}
	electing = true
	mu.Unlock()

	gotOK := false
	for n := id + 1; n < total; n++ {
		logf("kirim ELECTION ke %d", n)
		r, ok := send(n, fmt.Sprintf("ELECTION:%d", id))
		if ok && r == "OK" {
			logf("terima OK dari %d", n)
			gotOK = true
		} else {
			logf("node %d tidak menjawab", n)
		}
	}

	if gotOK {
		logf("ada node lebih tinggi yang menjawab, diam")
		return
	}

	mu.Lock()
	coordinator = id
	mu.Unlock()
	logf("menjadi COORDINATOR")
	for n := 0; n < id; n++ {
		logf("kirim COORDINATOR ke %d", n)
		if _, ok := send(n, fmt.Sprintf("COORDINATOR:%d", id)); !ok {
			logf("node %d tidak menjawab COORDINATOR", n)
		}
	}
}

func serve(s mangos.Socket) {
	for {
		b, err := s.Recv()
		if err != nil {
			return
		}
		parts := strings.Split(string(b), ":")
		if len(parts) != 2 {
			s.Send([]byte("ERR"))
			continue
		}
		from, _ := strconv.Atoi(parts[1])
		switch parts[0] {
		case "ELECTION":
			logf("terima ELECTION dari %d", from)
			s.Send([]byte("OK"))
			if from < id {
				logf("kirim OK ke %d", from)
				go startElection()
			}
		case "COORDINATOR":
			mu.Lock()
			coordinator = from
			mu.Unlock()
			logf("terima COORDINATOR, koordinator baru adalah node %d", from)
			s.Send([]byte("ACK"))
		default:
			s.Send([]byte("ERR"))
		}
	}
}

func main() {
	if len(os.Args) < 2 {
		fmt.Println("usage: ./bully <id> [live|live_init|dead]")
		os.Exit(1)
	}
	n, err := strconv.Atoi(os.Args[1])
	if err != nil || n < 0 || n >= total {
		fmt.Println("id harus 0..7")
		os.Exit(1)
	}
	id = n

	mode := "live"
	if len(os.Args) >= 3 {
		mode = os.Args[2]
	} else if id == total-1 {
		mode = "dead"
	} else if id == 4 {
		mode = "live_init"
	}

	if mode == "dead" {
		logf("mati")
		return
	}

	s, err := rep.NewSocket()
	if err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
	defer s.Close()
	if err := s.Listen(addr(id)); err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
	logf("hidup di %s", addr(id))
	go serve(s)

	if mode == "live_init" {
		time.Sleep(2 * time.Second)
		logf("mendeteksi node %d mati, memulai election", total-1)
		go startElection()
	}

	time.Sleep(8 * time.Second)
	logf("selesai, koordinator = %d", coordinator)
}