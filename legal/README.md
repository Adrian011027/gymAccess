# Documentos legales — borradores

> **Estos son borradores técnicos, no asesoría legal.** Los redactó el equipo de
> desarrollo a partir de lo que el sistema realmente hace y de lo que exige la
> LFPDPPP. **Antes de usarlos hay que llevarlos a un abogado**, que es quien puede
> confirmar que cubren tu caso y adaptarlos a tu situación fiscal y societaria.
>
> Los espacios entre `[corchetes]` son datos que debes rellenar tú.

## Qué protege cada documento

| Archivo | Quién lo emite | A quién protege | ¿Obligatorio? |
|---|---|---|---|
| `aviso-privacidad.md` | El dueño del gym → sus socios | Al gym | **Sí** (LFPDPPP arts. 15-18) |
| `terminos-servicio.md` | El proveedor del software → el gym | Al proveedor | No, pero sin él no hay límite de responsabilidad |
| `convenio-encargado.md` | Ambos lo firman | **A los dos** | **Sí** en la práctica (LFPDPPP art. 3 fr. IX y RLFPDPPP art. 51) |

El tercero es el que suele faltar y el que más importa. Delimita que el gym decide
qué datos se tratan y para qué (es el **responsable**), y que el proveedor solo los
opera por cuenta del gym (es el **encargado**). Sin esa separación por escrito, ante
un incidente no hay nada que distinga a quien decidió tratar los datos de quien solo
mantiene el servidor.

## Cómo se cargan al sistema

El aviso de privacidad se publica desde **Configuración → Legal** en la aplicación.
Los términos y el convenio los publica el proveedor:

```bash
python manage.py cargar_documentos_legales
```

Cada publicación crea una **versión nueva**; el texto de una versión ya aceptada por
alguien no se puede editar, porque eso rompería la evidencia: quien la firmó habría
aceptado otra cosa.

## Qué exige la ley que el sistema pueda hacer

- **Registrar el consentimiento** con versión y fecha → `legal.ConsentimientoSocio`
- **Atender derechos ARCO en 20 días hábiles** → `GET /api/socios/{id}/datos-personales/`
  y `POST /api/socios/{id}/cancelar-datos/`
- **Consentimiento del tutor para menores** → campos `tutor_*` en `Socio`, obligatorios
  cuando la fecha de nacimiento indica menos de 18 años

## Riesgos técnicos aún abiertos

Están detallados en `../consideraciones_produccion.md`. Los relevantes para privacidad:

- La base de datos **no está cifrada en reposo**. Antes de producción debería estarlo.
- Los tokens JWT viven en `localStorage`: un XSS los expondría.
- No hay política de retención automática: los datos de socios dados de baja se
  conservan indefinidamente salvo que se ejerza la cancelación a mano.
- **El lector de huella se retiró.** Fue una decisión afortunada: los datos
  biométricos son *datos personales sensibles* (art. 3 fr. VI) y exigen consentimiento
  expreso y por escrito, con la carga de la prueba sobre el responsable. Si algún día
  se reactiva, este paquete de documentos **no basta** y hay que rehacerlo.
