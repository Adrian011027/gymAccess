# Análisis de recursos: ¿cabe gymAccess en el droplet del SaaS de spas?

Fecha del análisis: 2026-07-19 · Droplet: `saas-ritual` (Digital Ocean)

Objetivo: decidir si gymAccess puede desplegarse en el **mismo droplet** donde ya corre en
producción el SaaS de citas para spas (con otro dominio, vía nginx server blocks), o si se
necesita otro droplet.

**Criterio de decisión:** si `RAM available − pico histórico del spa (24-48 h) ≥ 500 MB`,
gymAccess cabe (necesita ~250 MB). Si no, hacer resize del droplet antes que crear uno nuevo.

---

## Los 3 comandos de medición

### 1. Foto instantánea del servidor
```bash
echo "=== NUCLEOS ==="; nproc; echo "=== RAM ==="; free -h; echo "=== DISCO ==="; df -h /; echo "=== TOP PROCESOS RAM ==="; ps aux --sort=-%mem | head -15
```

### 2. Logger de picos (dejar corriendo 24-48 h)
```bash
nohup bash -c 'while true; do echo "$(date "+%F %T") RAM_MB=$(free -m | awk "/Mem:/{print \$3}") CPU%=$(top -bn1 | grep "Cpu(s)" | awk "{print \$2+\$4}")"; sleep 60; done' >> ~/recursos_spa.log 2>/dev/null &
```
Consumo del propio logger: despreciable (<0.5% CPU, ~2 MB RAM, ~70 KB de log al día).
Para detenerlo al terminar: `pkill -f recursos_spa`

### 3. Leer los picos (al día siguiente)
```bash
sort -t= -k2 -n ~/recursos_spa.log | tail -5
```

---

## Resultados del comando 1 (2026-07-19)

```
=== NUCLEOS ===
2
=== RAM ===
               total        used        free      shared  buff/cache   available
Mem:           3.8Gi       2.5Gi       210Mi       144Mi       1.6Gi       1.3Gi
Swap:             0B          0B          0B
=== DISCO ===
/dev/vda1        77G   46G   32G  59% /
```

Procesos que más RAM consumen (RSS):

| Proceso | RAM | Nota |
|---|---|---|
| dockerd | 884 MB | el spa corre en Docker; el daemon solo ya usa 22% |
| node dist/main | 193 MB | backend Node |
| next-server v16 | 177 MB | frontend Next.js |
| daphne :8000 | 149 MB | Django ASGI |
| celery (beat + worker + 4 hijos) | ~660 MB | tareas asíncronas |
| postgres | ~240 MB | checkpointer + background writer |

### Lectura
- **1.3 GiB disponibles** de 3.8 GiB. CPU casi ociosa (todos los procesos en 0.0–0.4%).
- ⚠️ **Sin swap**: si la RAM se agota, el OOM killer de Linux mata procesos (podría tumbar el
  spa en producción). Recomendado agregar 2 GB de colchón:
  ```bash
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile && echo '/swapfile none swap sw 0 0' >> /etc/fstab
  ```

Estado: el logger (comando 2) quedó corriendo el 2026-07-19 (PID 589993).

---

## Consumo medido de gymAccess (prueba de carga local, 2026-07-19)

Prueba en 3 fases contra servidor Django aislado (BD desechable, settings tipo producción,
monitoreo del proceso cada segundo, rate limiting activo):

| Fase | RAM | CPU (100% = 1 núcleo) | Latencias |
|---|---|---|---|
| Reposo (15 s) | 54 MB | ~3% | — |
| Uso normal (60 s): 4 clientes con check-ins, dashboard cada 5 s, 2 altas | 55–56 MB | **~1%** | check-in 27 ms · dashboard 23 ms · alta 46 ms (p95 < 120 ms) |
| Pico bombardeado (30 s): 4 hilos sin pausa, 6,854 peticiones | **60 MB** | 150–185% | < 120 ms; el throttling respondió 429 a 6,465 peticiones |

Estimación en producción (gunicorn 2-3 workers + margen): **~150–250 MB RAM**, CPU marginal.
El uso real del gimnasio (3-4 clientes, tráfico por eventos: registro/check-in, no flujo
constante) corresponde a la fase "uso normal".

---

## Veredicto

**Preliminar (con el snapshot): SÍ cabe en el mismo droplet, con holgura.**
1.3 GiB disponibles vs ~250 MB necesarios → quedaría ~1 GB de margen, el doble del criterio.

**Definitivo:** pendiente de los picos de 24 h — correr el comando 3 (~2026-07-20) y comparar:
`1.3 GiB − (pico_RAM − 2.5 GiB actuales)` debe seguir dejando ≥ 500 MB tras sumar gymAccess.

Decisión pendiente al desplegar: gymAccess dentro de Docker (reutiliza el daemon que ya está
en RAM) o directo con systemd + gunicorn (más ligero). Ver también `consideraciones_produccion.md`
(checklist completo de despliegue, nginx server blocks para 2 dominios en la misma IP, Cloudflare).
