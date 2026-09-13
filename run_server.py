"""
Pil Paketi Termal Kaçak Simülatörü - Yerel Sunucu Başlatıcı
Kullanım: python run_server.py [--port 8000]
"""

import uvicorn
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Thermal Runaway Simulator API & Web UI Server")
    parser.add_argument("--host", default="127.0.0.1", help="Bağlanılacak host adresi")
    parser.add_argument("--port", type=int, default=8000, help="Çalıştırılacak port numarası")
    parser.add_argument("--reload", action="store_true", help="Canlı kod yenileme modu")
    args = parser.parse_args()

    print("=" * 70)
    print(">>> Pil Paketi Termal Kacak (Thermal Runaway) Simulatoru V1.0")
    print(f">>> Sunucu Adresi: http://{args.host}:{args.port}")
    print(f">>> API Dokumantasyonu (Swagger): http://{args.host}:{args.port}/docs")
    print("=" * 70)

    uvicorn.run("simulator.api.app:app", host=args.host, port=args.port, reload=args.reload)
