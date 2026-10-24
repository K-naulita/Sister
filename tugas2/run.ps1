go build -o bully.exe bully.go
foreach ($i in 0..6) {
    $m = if ($i -eq 4) { "live_init" } else { "live" }
    Start-Process -FilePath .\bully.exe -ArgumentList @("$i", $m) -NoNewWindow
}
.\bully.exe 7 dead
Start-Sleep -Seconds 10