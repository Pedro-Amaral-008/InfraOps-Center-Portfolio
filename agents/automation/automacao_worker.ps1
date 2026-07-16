[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$apiUrl = "http://IP_INTERNO_AQUI:8000"
$apiKey = "SUA_API_KEY_AQUI"
$telegramToken = "SEU_TELEGRAM_BOT_TOKEN_AQUI"
$telegramChatId = "SEU_TELEGRAM_CHAT_ID_AQUI"

$fluigIP = "10.10.0.5"
$userFluig = Get-Content "C:\Script\fluig_user.txt"
$passFluig = Get-Content "C:\Script\fluig_cred.txt" | ConvertTo-SecureString
$credFluig = New-Object System.Management.Automation.PSCredential($userFluig, $passFluig)

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

$consulta = Invoke-RestMethod -Uri "$apiUrl/automations/jobs/pendente?alvo=srvfrotas" -Headers @{ "x-api-key" = $apiKey }

if ($consulta.tem_job -eq $false) {
    exit 0
}

$jobId = $consulta.job_id
$tipo = $consulta.tipo

Write-Host "Job encontrado: ID $jobId, Tipo $tipo"

if ($tipo -eq "restart_fluig") {
    Enviar-Telegram "🔔 *Monitoramento InfraOps Center*`n`n*REINICIANDO FLUIG* 🔄`n`nIniciando sequência de reinicialização dos serviços."

    try {
        Invoke-Command -ComputerName $fluigIP -Credential $credFluig -ScriptBlock {
            Stop-Service -Name "fluig" -Force -ErrorAction SilentlyContinue
        }
        Start-Sleep -Seconds 10

        Invoke-Command -ComputerName $fluigIP -Credential $credFluig -ScriptBlock {
            Stop-Service -Name "fluig_Indexer" -Force -ErrorAction SilentlyContinue
        }
        Start-Sleep -Seconds 10

        Invoke-Command -ComputerName $fluigIP -Credential $credFluig -ScriptBlock {
            Stop-Service -Name "fluig_RealTime" -Force -ErrorAction SilentlyContinue
        }
        Start-Sleep -Seconds 10

        Invoke-Command -ComputerName $fluigIP -Credential $credFluig -ScriptBlock {
            Start-Service -Name "fluig_Indexer" -ErrorAction SilentlyContinue
        }
        Start-Sleep -Seconds 10

        Invoke-Command -ComputerName $fluigIP -Credential $credFluig -ScriptBlock {
            Start-Service -Name "fluig_RealTime" -ErrorAction SilentlyContinue
        }
        Start-Sleep -Seconds 10

        Invoke-Command -ComputerName $fluigIP -Credential $credFluig -ScriptBlock {
            Start-Service -Name "fluig" -ErrorAction SilentlyContinue
        }
        Start-Sleep -Seconds 20

        $statusFinal = Invoke-Command -ComputerName $fluigIP -Credential $credFluig -ScriptBlock {
            Get-Service -Name "fluig", "fluig_Indexer", "fluig_RealTime" | Select-Object Name, Status
        }

        $todosRodando = ($statusFinal | Where-Object { $_.Status.ToString() -ne "Running" }).Count -eq 0

        if ($todosRodando) {
            $resumo = ($statusFinal | ForEach-Object { "$($_.Name): $($_.Status.ToString())" }) -join "`n"
            Enviar-Telegram "🔔 *Monitoramento InfraOps Center*`n`n*FLUIG REINICIADO COM SUCESSO* ✅`n`n$resumo`n`n🕐 *Horário:* $(Get-Date -Format 'dd/MM/yyyy HH:mm:ss')"

            $detalheEncoded = [uri]::EscapeDataString("Fluig reiniciado com sucesso: fluig, fluig_Indexer e fluig_RealTime online")
            Invoke-RestMethod -Uri "$apiUrl/automations/jobs/$jobId/concluir?resultado=sucesso&detalhe=$detalheEncoded" -Method Post -Headers @{ "x-api-key" = $apiKey }
        }
        else {
            $resumo = ($statusFinal | ForEach-Object { "$($_.Name): $($_.Status.ToString())" }) -join "`n"
            Enviar-Telegram "🔔 *Monitoramento InfraOps Center*`n`n*FALHA AO REINICIAR FLUIG* ❌`n`n$resumo`n`n⚠️ *Ação:* Verificar servidor manualmente"

            $detalheEncoded = [uri]::EscapeDataString("Falha ao reiniciar Fluig: $resumo")
            Invoke-RestMethod -Uri "$apiUrl/automations/jobs/$jobId/concluir?resultado=erro&detalhe=$detalheEncoded" -Method Post -Headers @{ "x-api-key" = $apiKey }
        }
    }
    catch {
        Enviar-Telegram "🔔 *Monitoramento InfraOps Center*`n`n*ERRO AO REINICIAR FLUIG* ❌`n`n$_`n`n⚠️ *Ação:* Verificar servidor manualmente"

        $detalheEncoded = [uri]::EscapeDataString("Erro ao reiniciar Fluig: $_")
        Invoke-RestMethod -Uri "$apiUrl/automations/jobs/$jobId/concluir?resultado=erro&detalhe=$detalheEncoded" -Method Post -Headers @{ "x-api-key" = $apiKey }
    }
}
