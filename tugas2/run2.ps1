go build -o bully.exe bully.go
foreach ($i in 0..6) {
    Start-Process -FilePath .\bully.exe -ArgumentList @("$i") -NoNewWindow
}
.\bully.exe 7
Start-Sleep -Seconds 10