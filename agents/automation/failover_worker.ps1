[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$apiUrl = "http://IP_INTERNO_AQUI:8000"
$apiKey = "SUA_API_KEY_AQUI"
$telegramToken = "SEU_TELEGRAM_BOT_TOKEN_AQUI"
$telegramChatId = "SEU_TELEGRAM_CHAT_ID_AQUI"

$interface = "Ethernet"
$ipAtual = "IP_INTERNO_AQUI"
$ipNovo = "IP_INTERNO_AQUI"
$prefixo = 24
$gateway = "IP_INTERNO_AQUI"

function Enviar-Telegram($mensagem) {
    try {
        $body = @{
            chat_id    = $telegramChatId
            text       = $mensagem
            parse_mode = "Markdown"
        } | ConvertTo-Json -Compress

        Invoke-RestMethod `
            -Uri ("https://api.telegram.org/bot" + $telegramToken + "/sendMessage") `
            -Method POST `
            -ContentType "application/json; charset=utf-8" `
            -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
    }
    catch {
        Write-Host "Erro ao enviar Telegram: $_"
    }
}

$consulta = Invoke-RestMethod -Uri "$apiUrl/automations/jobs/pendente?alvo=srvarqred" -Headers @{ "x-api-key" = $apiKey }

if ($consulta.tem_job -eq $false) {
    exit 0
}

$jobId = $consulta.job_id
$tipo = $consulta.tipo

Write-Host "Job encontrado: ID $jobId, Tipo $tipo"

if ($tipo -eq "failover_srv_arquivos") {

    $aindaOnline = Test-Connection -ComputerName $ipNovo -Count 2 -Quiet

    if ($aindaOnline) {
        Enviar-Telegram "🔔 *Monitoramento InfraOps Center*`n`n*FAILOVER CANCELADO POR SEGURANÇA* ⚠️`n`nO servidor $ipNovo ainda está respondendo. Failover não foi executado para evitar conflito de IP.`n`n🕐 *Horário:* $(Get-Date -Format 'dd/MM/yyyy HH:mm:ss')"

        $detalheEncoded = [uri]::EscapeDataString("Failover cancelado: $ipNovo ainda esta online")
        Invoke-RestMethod -Uri "$apiUrl/automations/jobs/$jobId/concluir?resultado=erro&detalhe=$detalheEncoded" -Method Post -Headers @{ "x-api-key" = $apiKey }
        exit 0
    }

    Enviar-Telegram "🔔 *Monitoramento InfraOps Center*`n`n*FAILOVER INICIADO* 🔄`n`nTrocando IP do SrvArqRed de $ipAtual para $ipNovo..."

    try {
        Remove-NetIPAddress -InterfaceAlias $interface -IPAddress $ipAtual -Confirm:$false -ErrorAction Stop

        New-NetIPAddress -InterfaceAlias $interface -IPAddress $ipNovo -PrefixLength $prefixo -DefaultGateway $gateway -ErrorAction Stop

        Start-Sleep -Seconds 5

        $confirmacao = Get-NetIPAddress -InterfaceAlias $interface -AddressFamily IPv4 | Where-Object { $_.IPAddress -eq $ipNovo }

        if ($confirmacao) {
            Enviar-Telegram "🔔 *Monitoramento InfraOps Center*`n`n*FAILOVER CONCLUÍDO COM SUCESSO* ✅`n`nSrvArqRed agora está respondendo em $ipNovo`n`n🕐 *Horário:* $(Get-Date -Format 'dd/MM/yyyy HH:mm:ss')"

            $detalheEncoded = [uri]::EscapeDataString("Failover concluido: SrvArqRed assumiu o IP $ipNovo")
            Invoke-RestMethod -Uri "$apiUrl/automations/jobs/$jobId/concluir?resultado=sucesso&detalhe=$detalheEncoded" -Method Post -Headers @{ "x-api-key" = $apiKey }
        }
        else {
            Enviar-Telegram "🔔 *Monitoramento InfraOps Center*`n`n*FALHA NO FAILOVER* ❌`n`nO IP $ipNovo não foi confirmado após a troca. Verificar manualmente."

            $detalheEncoded = [uri]::EscapeDataString("Falha no failover: IP $ipNovo nao confirmado")
            Invoke-RestMethod -Uri "$apiUrl/automations/jobs/$jobId/concluir?resultado=erro&detalhe=$detalheEncoded" -Method Post -Headers @{ "x-api-key" = $apiKey }
        }
    }
    catch {
        Enviar-Telegram "🔔 *Monitoramento InfraOps Center*`n`n*ERRO NO FAILOVER* ❌`n`n$_`n`n⚠️ *Ação:* Verificar servidor manualmente"

        $detalheEncoded = [uri]::EscapeDataString("Erro no failover: $_")
        Invoke-RestMethod -Uri "$apiUrl/automations/jobs/$jobId/concluir?resultado=erro&detalhe=$detalheEncoded" -Method Post -Headers @{ "x-api-key" = $apiKey }
    }
}
