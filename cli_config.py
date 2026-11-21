#!/usr/bin/env python3
"""
CLI Local - Configuración guiada para Deriv Bot
Permite configurar y desplegar el bot desde local.
Uso:
  python cli_config.py              # modo interactivo
  python cli_config.py --mode multiplier --symbol R_50 --stake 20 --deploy
"""
import argparse
import json
import os
import subprocess
import sys

CONFIG_FILE = "config.json"

SYMBOLS = [
    "1HZ50V", "R_50", "R_100", "R_25", "R_10",
    "1HZ10V", "1HZ25V", "1HZ75V", "1HZ100V"
]

DEFAULTS = {
    "DERIV_BOT_MODE": "binary",
    "DERIV_SYMBOL": "1HZ50V",
    "DERIV_STAKE": "10.0",
    "DERIV_HMA_PERIOD": "30",
    "DERIV_FLOW_PERIOD": "14",
    "DERIV_FLOW_SMOOTH": "3",
    "DERIV_FLOW_THRESHOLD": "0.3",
    "DERIV_DURATION": "1",
    "DERIV_DURATION_UNIT": "m",
    "DERIV_MARTINGALE_MULT": "2.4",
    "DERIV_MAX_MARTINGALE_STEPS": "10",
    "DERIV_MULTIPLIER": "100",
    "DERIV_TP_PCT": "0.001",
    "DERIV_SL_PCT": "0.001",
    "DERIV_LOG_LEVEL": "INFO",
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {}

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

def print_config(cfg):
    mode = cfg.get("DERIV_BOT_MODE", "binary")
    print(f"\n📋 Configuración:")
    print(f"  Modo:          {mode}")
    print(f"  Símbolo:       {cfg.get('DERIV_SYMBOL', '1HZ50V')}")
    print(f"  Stake:         ${cfg.get('DERIV_STAKE', '10.0')}")
    print(f"  HMA Period:    {cfg.get('DERIV_HMA_PERIOD', '30')}")
    print(f"  Flow Period:   {cfg.get('DERIV_FLOW_PERIOD', '14')}")
    print(f"  Flow Smooth:   {cfg.get('DERIV_FLOW_SMOOTH', '3')}")
    print(f"  Flow Thresh:   {cfg.get('DERIV_FLOW_THRESHOLD', '0.3')}")
    if mode == "binary":
        print(f"  Duración:      {cfg.get('DERIV_DURATION', '1')} {cfg.get('DERIV_DURATION_UNIT', 'm')}")
        print(f"  Martingala:    x{cfg.get('DERIV_MARTINGALE_MULT', '2.4')} (max {cfg.get('DERIV_MAX_MARTINGALE_STEPS', '10')} steps)")
    else:
        print(f"  Multiplier:    x{cfg.get('DERIV_MULTIPLIER', '100')}")
        print(f"  TP/SL:         {float(cfg.get('DERIV_TP_PCT', '0.001'))*100:.3f}% / {float(cfg.get('DERIV_SL_PCT', '0.001'))*100:.3f}%")

def deploy_to_render():
    print("\n🚀 Desplegando a Render...")
    try:
        subprocess.run(["git", "add", "config.json"], check=True)
        subprocess.run(["git", "commit", "-m", "config: actualización desde CLI local"], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        subprocess.run(["render", "deploys", "create", "srv-dbqldtlg1s2s73emqk30", "--wait", "--confirm", "--clear-cache"], check=True)
        print("  ✅ Deploy completado")
    except subprocess.CalledProcessError as e:
        print(f"  ❌ Error en deploy: {e}")

def check_status():
    try:
        import urllib.request
        r = urllib.request.urlopen("https://deriv-py-bot.onrender.com/status", timeout=10)
        print(r.read().decode())
    except Exception as e:
        print(f"  ❌ Error: {e}")

def interactive_mode(cfg):
    while True:
        print_config(cfg)
        print("\n📋 MENÚ:")
        print("  1. Cambiar modo (Binary/Multiplier)")
        print("  2. Cambiar símbolo")
        print("  3. Cambiar stake")
        print("  4. Configurar HMA + Flow")
        if cfg.get("DERIV_BOT_MODE") == "binary":
            print("  5. Configurar Binary (duración, martingala)")
        else:
            print("  5. Configurar Multiplier (multiplier, TP, SL)")
        print("  6. Guardar config.json local")
        print("  7. Desplegar a Render")
        print("  8. Ver estado del bot en Render")
        print("  0. Salir")
        
        try:
            choice = input("\n  > ").strip()
        except EOFError:
            break
        
        if choice == "1":
            mode = input("  Modo (binary/multiplier): ").strip().lower()
            if mode in ("binary", "multiplier"):
                cfg["DERIV_BOT_MODE"] = mode
                print(f"  ✅ Modo: {mode}")
        elif choice == "2":
            print("Símbolos:", ", ".join(SYMBOLS))
            sym = input("  Símbolo: ").strip().upper()
            if sym in SYMBOLS:
                cfg["DERIV_SYMBOL"] = sym
                print(f"  ✅ Símbolo: {sym}")
        elif choice == "3":
            val = input(f"  Stake [{cfg.get('DERIV_STAKE', '10.0')}]: ").strip()
            if val:
                cfg["DERIV_STAKE"] = val
                print(f"  ✅ Stake: ${val}")
        elif choice == "4":
            cfg["DERIV_HMA_PERIOD"] = input(f"  HMA Period [{cfg.get('DERIV_HMA_PERIOD', '30')}]: ").strip() or cfg.get('DERIV_HMA_PERIOD', '30')
            cfg["DERIV_FLOW_PERIOD"] = input(f"  Flow Period [{cfg.get('DERIV_FLOW_PERIOD', '14')}]: ").strip() or cfg.get('DERIV_FLOW_PERIOD', '14')
            cfg["DERIV_FLOW_SMOOTH"] = input(f"  Flow Smooth [{cfg.get('DERIV_FLOW_SMOOTH', '3')}]: ").strip() or cfg.get('DERIV_FLOW_SMOOTH', '3')
            cfg["DERIV_FLOW_THRESHOLD"] = input(f"  Flow Threshold [{cfg.get('DERIV_FLOW_THRESHOLD', '0.3')}]: ").strip() or cfg.get('DERIV_FLOW_THRESHOLD', '0.3')
            print("  ✅ HMA + Flow actualizados")
        elif choice == "5":
            if cfg.get("DERIV_BOT_MODE") == "binary":
                cfg["DERIV_DURATION"] = input(f"  Duración min [{cfg.get('DERIV_DURATION', '1')}]: ").strip() or cfg.get('DERIV_DURATION', '1')
                cfg["DERIV_MARTINGALE_MULT"] = input(f"  Martingala Mult [{cfg.get('DERIV_MARTINGALE_MULT', '2.4')}]: ").strip() or cfg.get('DERIV_MARTINGALE_MULT', '2.4')
                cfg["DERIV_MAX_MARTINGALE_STEPS"] = input(f"  Max Steps [{cfg.get('DERIV_MAX_MARTINGALE_STEPS', '10')}]: ").strip() or cfg.get('DERIV_MAX_MARTINGALE_STEPS', '10')
            else:
                cfg["DERIV_MULTIPLIER"] = input(f"  Multiplier x[{cfg.get('DERIV_MULTIPLIER', '100')}]: ").strip() or cfg.get('DERIV_MULTIPLIER', '100')
                cfg["DERIV_TP_PCT"] = input(f"  TP % [{cfg.get('DERIV_TP_PCT', '0.001')}]: ").strip() or cfg.get('DERIV_TP_PCT', '0.001')
                cfg["DERIV_SL_PCT"] = input(f"  SL % [{cfg.get('DERIV_SL_PCT', '0.001')}]: ").strip() or cfg.get('DERIV_SL_PCT', '0.001')
            print("  ✅ Opciones actualizadas")
        elif choice == "6":
            save_config(cfg)
            print("  ✅ Config guardada en config.json")
        elif choice == "7":
            save_config(cfg)
            deploy_to_render()
        elif choice == "8":
            check_status()
        elif choice == "0":
            break

def main():
    parser = argparse.ArgumentParser(description="Deriv Bot CLI - Configuración y despliegue")
    parser.add_argument("--mode", choices=["binary", "multiplier"], help="Modo de operación")
    parser.add_argument("--symbol", choices=SYMBOLS, help="Símbolo a operar")
    parser.add_argument("--stake", type=float, help="Stake base en USD")
    parser.add_argument("--deploy", action="store_true", help="Desplegar a Render tras cambios")
    parser.add_argument("--status", action="store_true", help="Ver estado del bot en Render")
    parser.add_argument("--interactive", action="store_true", help="Modo interactivo (default si no hay args)")
    args = parser.parse_args()

    cfg = load_config()
    for k, v in DEFAULTS.items():
        cfg.setdefault(k, v)

    # Aplicar args
    if args.mode: cfg["DERIV_BOT_MODE"] = args.mode
    if args.symbol: cfg["DERIV_SYMBOL"] = args.symbol
    if args.stake: cfg["DERIV_STAKE"] = str(args.stake)
    if args.status: check_status()

    if any([args.mode, args.symbol, args.stake]):
        save_config(cfg)
        print_config(cfg)

    if args.deploy:
        deploy_to_render()

    # Si no hay args o --interactive, modo interactivo
    if not any([args.mode, args.symbol, args.stake, args.deploy, args.status]) or args.interactive:
        interactive_mode(cfg)

if __name__ == "__main__":
    main()