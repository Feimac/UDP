# Transferência de Arquivos Confiável sobre UDP

Este projeto implementa um sistema cliente-servidor para a transferência de arquivos de forma confiável utilizando o protocolo UDP. Como o UDP não oferece garantias de entrega, ordenação ou integridade dos pacotes, foi desenvolvido um protocolo de aplicação simples sobre ele para adicionar essas funcionalidades essenciais.

## Visão Geral

O objetivo é simular mecanismos de confiabilidade que são nativos do TCP, como a detecção de erros, a ordenação de pacotes e a recuperação de perdas, diretamente na camada de aplicação.

A solução é composta por três arquivos principais:

  - `server.py`: O servidor que aguarda requisições de clientes, segmenta e envia os arquivos solicitados.
  - `client.py`: O cliente que requisita um arquivo, recebe os segmentos, verifica sua integridade, os ordena e solicita a retransmissão de segmentos perdidos ou corrompidos.
  - `protocol.py`: Um módulo auxiliar que define a estrutura do cabeçalho dos pacotes e funções para empacotar e desempacotar os dados.

## Protocolo de Aplicação

Para garantir a confiabilidade, foi criado um protocolo simples que define a comunicação entre cliente e servidor.

### 1\. Requisição de Arquivo (Cliente -\> Servidor)

O cliente inicia a comunicação enviando uma mensagem de texto simples para o servidor, no formato:

```
GET /caminho/do/arquivo.ext
```

### 2\. Resposta do Servidor (Servidor -\> Cliente)

  - **Sucesso**: Se o arquivo existir, o servidor responde com uma mensagem de confirmação:

    ```
    OK <tamanho_total_bytes> <tamanho_chunk> <total_chunks>
    ```

    Onde:

      - `tamanho_total_bytes`: O tamanho completo do arquivo.
      - `tamanho_chunk`: O tamanho de cada segmento de dados (payload).
      - `total_chunks`: O número total de segmentos que serão enviados.

  - **Erro**: Se o arquivo não for encontrado, o servidor envia:

    ```
    ERROR:NOTFOUND
    ```

### 3\. Transmissão de Dados (Servidor -\> Cliente)

Após a confirmação "OK", o servidor começa a enviar os segmentos do arquivo. Cada pacote de dados possui um cabeçalho customizado, definido em `protocol.py`, com a seguinte estrutura:

  - **Número de Sequência (4 bytes)**: Um inteiro que indica a posição do segmento no arquivo, essencial para a ordenação no cliente.
  - **Tamanho do Payload (4 bytes)**: O tamanho dos dados úteis no pacote.
  - **Checksum MD5 (16 bytes)**: O hash MD5 do payload, usado para verificar a integridade dos dados.

O servidor envia todos os pacotes em sequência e, ao final, envia uma mensagem `END` para sinalizar o término da primeira rodada de envio.

### 4\. Recuperação de Erros (Cliente -\> Servidor)

Após a primeira rodada, o cliente analisa os pacotes recebidos. Ele identifica quais segmentos estão faltando (com base nos números de sequência) e quais estão corrompidos (comparando o checksum MD5).

Com essa lista, o cliente envia uma mensagem de `NACK` (Negative Acknowledgement) ao servidor:

```
NACK <seq1>,<seq2>,<seq3>,...
```

Onde `<seq1>,<seq2>` são os números de sequência dos segmentos que precisam ser reenviados.

### 5\. Retransmissão (Servidor -\> Cliente)

Ao receber um `NACK`, o servidor reenviara apenas os segmentos solicitados, finalizando com outra mensagem `END`. Este ciclo de `NACK` e retransmissão se repete até que o cliente tenha recebido todos os segmentos de forma íntegra.

### 6\. Finalização (Cliente -\> Servidor)

Quando o cliente consegue montar o arquivo completo e verificado, ele envia uma mensagem `COMPLETE` ao servidor, encerrando a sessão de transferência para aquele arquivo.

## Como Executar

### Pré-requisitos

  - Python 3

### 1\. Iniciar o Servidor

O servidor precisa ser executado primeiro. Ele recebe dois argumentos: a porta em que vai operar e a pasta a partir da qual os arquivos serão servidos.

**Sintaxe:**

```bash
python3 server.py <porta> <pasta_de_arquivos>
```

**Exemplo:**
Para rodar o servidor na porta `8080` e servir arquivos da pasta `./arquivos_disponiveis`:

```bash
mkdir arquivos_disponiveis
# Adicione um arquivo grande nesta pasta, por exemplo, 'documento.zip'
python3 server.py 8080 ./arquivos_disponiveis
```

O servidor ficará ativo, aguardando conexões.

### 2\. Executar o Cliente

O cliente solicita um arquivo ao servidor. Ele requer um argumento principal no formato `@IP_DO_SERVIDOR:PORTA/NOME_DO_ARQUIVO`.

**Sintaxe:**

```bash
python3 client.py <target> [opções]
```

**Exemplo:**
Para solicitar o arquivo `documento.zip` do servidor rodando em `localhost` (127.0.0.1) na porta `8080`:

```bash
python3 client.py @127.0.0.1:8080/documento.zip
```

O arquivo recebido será salvo como `received_documento.zip` no mesmo diretório.

### 3\. Simulação de Perda de Pacotes

Para testar o mecanismo de recuperação de erros, o cliente possui uma opção `-d` ou `--drop` que permite especificar uma lista de números de sequência a serem descartados intencionalmente durante a primeira rodada de recebimento.

**Exemplo:**
Para solicitar o mesmo arquivo, mas simulando a perda dos segmentos 3, 7 e 9:

```bash
python3 client.py @127.0.0.1:8080/documento.zip --drop "3,7,9"
```

O cliente irá descartar esses pacotes, detectar sua ausência e solicitar a retransmissão via `NACK`, demonstrando a robustez do protocolo.
