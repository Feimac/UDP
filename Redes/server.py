

import socket
import sys
import os
from protocol import CHUNK_SIZE, make_data_packet

RETRANSMISSION_WAIT = 5.0  


def split_file_into_chunks(path, chunk_size=CHUNK_SIZE):
    with open(path, "rb") as f:
        idx = 0
        while True:
            data = f.read(chunk_size)
            if not data:
                break
            yield idx, data
            idx += 1


def handle_client_request(sock: socket.socket, client_addr, req_text, folder):
    req_text = req_text.strip()
    if not req_text.startswith("GET "):
        print("Requisição inválida:", req_text)
        return
    _, filename = req_text.split(" ", 1)

    safe_name = os.path.normpath(filename).lstrip(os.sep)
    filepath = os.path.join(folder, safe_name)
    if not os.path.isfile(filepath):
        err = "ERROR:NOTFOUND"
        sock.sendto(err.encode("utf-8"), client_addr)
        print(f"[{client_addr}] Arquivo não encontrado: {filepath}")
        return

    filesize = os.path.getsize(filepath)


    chunks = list(split_file_into_chunks(filepath))
    total_chunks = len(chunks)

    
    ok_msg = f"OK {filesize} {CHUNK_SIZE} {total_chunks}"
    sock.sendto(ok_msg.encode("utf-8"), client_addr)
    print(f"[{client_addr}] Enviando {filepath} ({filesize} bytes) em {total_chunks} chunks")

    
    for seq, payload in chunks:
        packet = make_data_packet(seq, payload)
        sock.sendto(packet, client_addr)

    
    sock.sendto(b"END", client_addr)
    print(f"[{client_addr}] Primeira rodada de envio concluída. Aguardando NACKs por {RETRANSMISSION_WAIT}s")

    
    sock.settimeout(RETRANSMISSION_WAIT)
    while True:
        try:
            data, addr = sock.recvfrom(8192)
        except socket.timeout:
            # tempo esgotado: sem NACKs; considera finalizado
            print(f"[{client_addr}] Timeout aguardando NACKs. Finalizando sessão.")
            break

        if addr != client_addr:
            # ignora outras fontes (poderíamos tratar múltiplos clientes em paralelo com threading)
            print("Mensagem de outro endereço ignorada:", addr)
            continue

        text = data.decode("utf-8", errors="ignore").strip()
        if text == "COMPLETE":
            print(f"[{client_addr}] Cliente confirmou recebimento completo.")
            break
        if text.startswith("NACK"):
            
            parts = text.split(" ", 1)
            if len(parts) < 2 or not parts[1].strip():
                print("NACK sem conteúdo")
                continue

            seq_list = [int(s) for s in parts[1].split(",") if s.strip().isdigit()]
            print(f"[{client_addr}] Recebido NACK para {len(seq_list)} segmentos: {seq_list[:10]}{'...' if len(seq_list)>10 else ''}")

            for seq in seq_list:
                if 0 <= seq < total_chunks:
                    with open(filepath, "rb") as f:
                        f.seek(seq * CHUNK_SIZE)
                        payload = f.read(CHUNK_SIZE)
                    packet = make_data_packet(seq, payload)
                    sock.sendto(packet, client_addr)

            
            sock.sendto(b"END", client_addr)
            print(f"[{client_addr}] Retransmissões enviadas. Aguardando novos pedidos.")
        else:
            print(f"[{client_addr}] Mensagem recebida: {text}")


def main():
    if len(sys.argv) < 3:
        print("Uso: python3 server.py <port> <folder>")
        sys.exit(1)

    port = int(sys.argv[1])
    folder = sys.argv[2]

    if not os.path.isdir(folder):
        print("Pasta inválida:", folder)
        sys.exit(1)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", port))
    sock.settimeout(5.0)  #

    print(f"Servidor UDP rodando na porta {port}. Pasta de arquivos: {folder}")

    try:
        while True:
            try:
                data, addr = sock.recvfrom(4096)
            except socket.timeout:
                # sem requisições novas → só continua
                continue

            try:
                text = data.decode("utf-8", errors="ignore")
            except Exception:
                text = ""

            if not text.strip():
                continue

            print(f"Requisição de {addr}: {text.strip()}")
            handle_client_request(sock, addr, text, folder)

    except KeyboardInterrupt:
        print("\nServidor finalizando (Ctrl+C).")
    finally:
        sock.close()


if __name__ == "__main__":
    main()
