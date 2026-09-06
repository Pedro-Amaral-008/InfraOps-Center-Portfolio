[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$apiUrl = "http://IP_INTERNO_AQUI:8000"
$apiKey = "SUA_API_KEY_AQUI"
$telegramChatId = "-1003927527414"

$interface = "Ethernet"
$ipAtual = "IP_ATUAL_AQUI"
$ipNovo = "IP_NOVO_AQUI"
$prefixo = 24
$gateway = "IP_GATEWAY_AQUI"

function Enviar-Telegram($mensagem) {
    try {
        $mensagemEncoded = [uri]::EscapeDataString($mensagem)
        Invoke-RestMethod -Uri "$apiUrl/automations/notificar-telegram?mensagem=$mensagemEncoded" -Method Post -Headers @{ "x-api-key" = $apiKey }
    }
    catch {
        Write-Host "Erro ao enviar Telegram: $_"
    }
}

function Trocar-IP($interfaceAlias, $ipOrigem, $ipDestino, $prefixoDestino, $gatewayDestino) {
    # Remove qualquer gateway padrao existente na interface antes de adicionar o novo IP,
    # senao o Windows recusa com "Instance DefaultGateway already exists".
    Get-NetRoute -InterfaceAlias $interfaceAlias -DestinationPrefix "0.0.0.0/0" -ErrorAction SilentlyContinue | Remove-NetRoute -Confirm:$false -ErrorAction SilentlyContinue

    # Adiciona o IP novo PRIMEIRO (sem remover o antigo ainda), assim a interface
    # nunca fica sem nenhum IP configurado no meio do processo.
    New-NetIPAddress -InterfaceAlias $interfaceAlias -IPAddress $ipDestino -PrefixLength $prefixoDestino -DefaultGateway $gatewayDestino -ErrorAction Stop | Out-Null

    Start-Sleep -Seconds 3

    $confirmouNovo = Get-NetIPAddress -InterfaceAlias $interfaceAlias -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -eq $ipDestino }

    if ($confirmouNovo) {
        # So remove o IP antigo depois de confirmar que o novo ja esta ativo.
        Remove-NetIPAddress -InterfaceAlias $interfaceAlias -IPAddress $ipOrigem -Confirm:$false -ErrorAction SilentlyContinue
    }

    Start-Sleep -Seconds 2

    return (Get-NetIPAddress -InterfaceAlias $interfaceAlias -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -eq $ipDestino })
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
        $confirmacao = Trocar-IP -interfaceAlias $interface -ipOrigem $ipAtual -ipDestino $ipNovo -prefixoDestino $prefixo -gatewayDestino $gateway

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
elseif ($tipo -eq "desfazer_failover_srv_arquivos") {
    $ipReversao = "IP_REVERSAO_AQUI"
    $ipOriginalReversao = "IP_ORIGINAL_REVERSAO_AQUI"

    Enviar-Telegram "🔔 *Monitoramento InfraOps Center*`n`n*REVERSÃO DE FAILOVER INICIADA* 🔄`n`nTrocando IP do SrvArqRed de $ipReversao de volta para $ipOriginalReversao..."

    try {
        $confirmacao = Trocar-IP -interfaceAlias $interface -ipOrigem $ipReversao -ipDestino $ipOriginalReversao -prefixoDestino $prefixo -gatewayDestino $gateway

        if ($confirmacao) {
            Enviar-Telegram "🔔 *Monitoramento InfraOps Center*`n`n*REVERSÃO CONCLUÍDA COM SUCESSO* ✅`n`nSrvArqRed voltou para o IP $ipOriginalReversao`n`n🕐 *Horário:* $(Get-Date -Format 'dd/MM/yyyy HH:mm:ss')"
            $detalheEncoded = [uri]::EscapeDataString("Reversao concluida: SrvArqRed voltou ao IP $ipOriginalReversao")
            Invoke-RestMethod -Uri "$apiUrl/automations/jobs/$jobId/concluir?resultado=sucesso&detalhe=$detalheEncoded" -Method Post -Headers @{ "x-api-key" = $apiKey }
        }
        else {
            Enviar-Telegram "🔔 *Monitoramento InfraOps Center*`n`n*FALHA NA REVERSÃO* ❌`n`nO IP $ipOriginalReversao não foi confirmado após a troca. Verificar manualmente."
            $detalheEncoded = [uri]::EscapeDataString("Falha na reversao: IP $ipOriginalReversao nao confirmado")
            Invoke-RestMethod -Uri "$apiUrl/automations/jobs/$jobId/concluir?resultado=erro&detalhe=$detalheEncoded" -Method Post -Headers @{ "x-api-key" = $apiKey }
        }
    }
    catch {
        Enviar-Telegram "🔔 *Monitoramento InfraOps Center*`n`n*ERRO NA REVERSÃO* ❌`n`n$_`n`n⚠️ *Ação:* Verificar servidor manualmente"
        $detalheEncoded = [uri]::EscapeDataString("Erro na reversao: $_")
        Invoke-RestMethod -Uri "$apiUrl/automations/jobs/$jobId/concluir?resultado=erro&detalhe=$detalheEncoded" -Method Post -Headers @{ "x-api-key" = $apiKey }
    }
}
