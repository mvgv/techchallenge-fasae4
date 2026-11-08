#!/usr/bin/env bash
# Provisiona os recursos Azure do MedWatch. Executar após `az login`.
# Uso: bash scripts/provision_azure.sh > azure.env   (a saída são linhas KEY=valor; copie para o .env)
set -euo pipefail
SUFFIX=${SUFFIX:-$RANDOM}
RG=${RG:-rg-medwatch}
LOC=${LOC:-brazilsouth}

# Mensagens do az vão para stderr, para que stdout contenha só as variáveis.
az group create -n "$RG" -l "$LOC" >&2
az cognitiveservices account create -n "medwatch-speech-$SUFFIX" -g "$RG" -l "$LOC" \
  --kind SpeechServices --sku S0 --yes >&2
az cognitiveservices account create -n "medwatch-lang-$SUFFIX" -g "$RG" -l "$LOC" \
  --kind TextAnalytics --sku S --yes >&2
az storage account create -n "medwatch$SUFFIX" -g "$RG" -l "$LOC" --sku Standard_LRS >&2
CONN=$(az storage account show-connection-string -n "medwatch$SUFFIX" -g "$RG" -o tsv)
az storage container create --name media --connection-string "$CONN" >&2
echo "AZURE_SPEECH_KEY=$(az cognitiveservices account keys list -n medwatch-speech-$SUFFIX -g $RG --query key1 -o tsv)"
echo "AZURE_SPEECH_REGION=$LOC"
echo "AZURE_LANGUAGE_KEY=$(az cognitiveservices account keys list -n medwatch-lang-$SUFFIX -g $RG --query key1 -o tsv)"
echo "AZURE_LANGUAGE_ENDPOINT=$(az cognitiveservices account show -n medwatch-lang-$SUFFIX -g $RG --query properties.endpoint -o tsv)"
echo "AZURE_STORAGE_CONNECTION_STRING=$CONN"
