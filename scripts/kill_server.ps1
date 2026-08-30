$p = Get-Content C:\Users\AMD\MK TRADER\scripts\.server_pid -ErrorAction SilentlyContinue
if ($p) {
    Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
}
