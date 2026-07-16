# ============================================
# INFRAOPS CENTER - WINDOWS AGENT
# Coleta CPU, RAM, Disco e Uptime do servidor
# ============================================

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$apiUrl = "http://IP_INTERNO_AQUI:8000/agents/metrics"
$apiKey = "SUA_API_KEY_AQUI"

$hostname = $env:COMPUTERNAME
$instance = $hostname.ToLower()

$cpuPercent = [math]::Round((Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average)

$os = Get-CimInstance Win32_OperatingSystem
$ramTotalGB = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
$ramFreeGB = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
$ramUsadaGB = $ramTotalGB - $ramFreeGB
$ramPercent = [math]::Round(($ramUsadaGB / $ramTotalGB) * 100)

$disco = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
$discoTotalGB = [math]::Round($disco.Size / 1GB, 1)
$discoLivreGB = [math]::Round($disco.FreeSpace / 1GB, 1)
$discoUsadoGB = $discoTotalGB - $discoLivreGB
$discoPercent = [math]::Round(($discoUsadoGB / $discoTotalGB) * 100)

$uptime = (Get-Date) - $os.LastBootUpTime
$uptimeHoras = [math]::Round($uptime.TotalHours)

$coletadoEm = [DateTimeOffset]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ss")

$body = @{
    hostname = $hostname
    instance = $instance
    cpu_percent = [int]$cpuPercent
    ram_percent = [int]$ramPercent
    ram_total_gb = [int]$ramTotalGB
    disco_percent = [int]$discoPercent
    disco_total_gb = [int]$discoTotalGB
    uptime_horas = [int]$uptimeHoras
    coletado_em = $coletadoEm
} | ConvertTo-Json

try {
    Invoke-RestMethod `
        -Uri $apiUrl `
        -Method Post `
        -Headers @{ "x-api-key" = $apiKey } `
        -ContentType "application/json; charset=utf-8" `
        -Body ([System.Text.Encoding]::UTF8.GetBytes($body))

    Write-Host "METRICAS ENVIADAS COM SUCESSO"
}
catch {
    Write-Host "ERRO AO ENVIAR METRICAS"
    Write-Host $_
}
