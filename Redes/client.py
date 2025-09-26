import socket
import sys
import time
import argparse
from protocol import parse_data_packet, md5_of_bytes

RECV_TIMEOUT = 5.0  

def parse_target(target: str):
    # formato: @IP:PORT/filename
    if not target.startswith("@"):
        raise ValueError("Target deve iniciar com @")
    body = target[1:]
    if "/" not in body:
        raise ValueError("Target deve conter '/' separando host:port e arquivo")
    hostport, filename = body.split("/", 1)
    if ":" not in hostport:
        raise ValueError("Host:Porto inválido")
    host, port_s = hostport.split(":", 1)
    return host, int(port_s), filename

def receive_round(sock, expected_total=None, drop_set=None):

    sock.settimeout(RECV_TIMEOUT)
    received = {}
    corrupted = []
    while True:
        try:
            data, addr = sock.recvfrom(65536)
        except socket.timeout:
            break
        
        if data == b"END":
            break
        try:
            txt = data.decode("utf-8")
            if txt.startswith("ERROR:"):
                return txt  
        except Exception:
            pass
        try:
            seq, payload_len, md5_bytes, payload = parse_data_packet(data)
        except Exception as e:
            print("Pacote inválido:", e)
            continue
        if drop_set and seq in drop_set:
            print(f"Simulação: descartando segmento {seq}")
            continue
        if md5_of_bytes(payload) != md5_bytes:
            print(f"Segmento {seq} com checksum inválido")
            corrupted.append(seq)
            
            continue
        
        received[seq] = payload
    return received, corrupted

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("target", help="Formato: @IP:PORT/filename")
    parser.add_argument("-d", "--drop", help="Lista de seqs para descartar (ex: 3,7,9)", default="")
    args = parser.parse_args()

    host, port, filename = parse_target(args.target)
    drop_set = set()
    if args.drop:
        for s in args.drop.split(","):
            s = s.strip()
            if s.isdigit():
                drop_set.add(int(s))

    server_addr = (host, port)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(5.0)


    req = f"GET {filename}"
    sock.sendto(req.encode("utf-8"), server_addr)
    print(f"Requisição enviada: {req} -> {server_addr}")

    try:
        data, addr = sock.recvfrom(4096)
    except socket.timeout:
        print("Timeout aguardando resposta do servidor.")
        sock.close()
        return
    text = data.decode("utf-8", errors="ignore").strip()
    if text.startswith("ERROR:"):
        print("Servidor respondeu erro:", text)
        sock.close()
        return
    if not text.startswith("OK"):
        print("Resposta inesperada do servidor:", text)
        sock.close()
        return
    parts = text.split()
    if len(parts) < 4:
        print("Resposta OK mal-formada:", text)
        sock.close()
        return
    filesize = int(parts[1]); chunksize = int(parts[2]); total_chunks = int(parts[3])
    print(f"Servidor pronto. filesize={filesize}, chunk_size={chunksize}, total_chunks={total_chunks}")

    # primeira rodada de recebimento
    received_map, corrupted = receive_round(sock, expected_total=total_chunks, drop_set=drop_set)
    if isinstance(received_map, str):  
        print("Erro do servidor:", received_map)
        sock.close()
        return

    print(f"Recebidos inicialmente: {len(received_map)} / {total_chunks}. Corrupções: {len(corrupted)}")
 
    while True:
        missing = [str(i) for i in range(total_chunks) if i not in received_map]
        corrupted = [str(i) for i in corrupted]
        to_request = missing + corrupted
        if not to_request:
            sock.sendto(b"COMPLETE", server_addr)
            print("Todos os segmentos recebidos e íntegros.")
            break
        nack_msg = "NACK " + ",".join(to_request)
        print(f"Solicitando retransmissão de {len(to_request)} segmentos (NACK). Exemplo: {to_request[:10]}")
        sock.sendto(nack_msg.encode("utf-8"), server_addr)
        result = receive_round(sock, expected_total=total_chunks, drop_set=None) 
        if isinstance(result, str):
            print("Erro durante retransmissão:", result)
            sock.close()
            return
        new_received, new_corrupted = result
        for k, v in new_received.items():
            received_map[k] = v
        corrupted = list(set([int(x) for x in corrupted] + new_corrupted))
        print(f"Agora: {len(received_map)} / {total_chunks} recebidos; corrupções: {len(corrupted)}")
        


    outname = args.out if args.out else ("received_" + filename.replace("/", "_"))
    with open(outname, "wb") as out:
        for i in range(total_chunks):
            out.write(received_map[i])
    print(f"Arquivo reconstruído salvo em: {outname} ({filesize} bytes esperados).")
    sock.close()

if __name__ == "__main__":
    main()
