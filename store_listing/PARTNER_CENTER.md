# Pliegue en Partner Center — qué llenar en cada sección

Producto: **Pliegue** · ID de la Store `9PB6SBF3HZVN` · tipo «Aplicación MSIX o PWA».
Identidad del paquete (ya está en el .msix; no se escribe en ningún lado):
`Blureck.Pliegue` · `CN=D0DDDE00-B489-49A9-A0D7-4208E98AF756` · `Blureck`.

Textos para copiar: `es-MX.md` (español) y `en-US.md` (inglés), en esta misma carpeta.

---

## 1. Precios y disponibilidad

- **Mercados:** todos los mercados (dejar la selección predeterminada).
- **Visibilidad / Descubrimiento:** Pública, se puede encontrar en la Store.
- **Programación:** publicar en cuanto se apruebe.
- **Precio base:** **Gratis**. Sin prueba gratuita, sin ventas.

## 2. Propiedades

- **Categoría:** `Productividad` (sin subcategoría).
- **URL de la directiva de privacidad:** `https://blureckzhyto.github.io/pliegue/privacidad.html`
- **Sitio web:** `https://blureckzhyto.github.io/pliegue/`
- **Información de contacto de soporte:** `https://github.com/Blureckzhyto/pliegue/issues`
- **Configuración del producto:**
  - «Este producto tiene acceso a información personal, la recopila o la transmite»: **No**.
  - «Este producto es compatible con la Pluma y la Tinta…», «Xbox», etc.: **No** (dejar sin marcar).
  - Compras en la app: **No**.
- **Requisitos del sistema:** no marcar nada (teclado y mouse son los habituales de una PC).

## 3. Clasificaciones por edades (cuestionario IARC)

- **Correo de contacto para la clasificación:** el tuyo.
- **Categoría de la app:** «Utilidad, productividad, comunicación u otra» (no es un juego).
- Respuestas:
  - Violencia, miedo, sexualidad, desnudez, lenguaje vulgar, drogas, alcohol, tabaco, apuestas, humor crudo: **No** a todo.
  - **¿Los usuarios pueden interactuar o intercambiar contenido entre sí?** No.
  - **¿Comparte la ubicación del usuario con otros?** No.
  - **¿Permite comprar bienes digitales?** No.
  - **¿Recopila o comparte información personal con terceros?** No.
  - **¿Da acceso sin restricciones a internet (como un navegador)?** **Sí**: solo en «HTML a PDF», cuando el usuario escribe una dirección web, la página se descarga para convertirla en PDF.
- Resultado esperado: apta para todos (IARC 3+ / PEGI 3 / ESRB Everyone), con el aviso «Acceso a internet sin restricciones».

## 4. Paquetes

- Sube **`Pliegue_1.4.0.0_x64.msix`** (del Escritorio o de `build\msix\`). Es el archivo **sin firmar**: la Store lo firma.
- Partner Center debería leer: versión 1.4.0.0, x64, «Windows 10 Desktop» (10.0.17763.0 o posterior), idiomas es-MX y en-US, capacidades `runFullTrust` e `internetClient`.
- **Familias de dispositivos:** solo **Windows 10/11 Desktop**.

## 5. Descripciones de Store (dos idiomas: Español (México) e Inglés (Estados Unidos))

Para cada idioma, desde `es-MX.md` / `en-US.md`:

- **Descripción**, **Novedades de esta versión**, **Características del producto** (una por campo) y **Descripción breve**.
- **Capturas de pantalla (Escritorio):** las 8 de `capturas\` en orden (01 a 08), con su leyenda.
- **Logotipos de Store:**
  - Póster 2:3 → `logos\poster-2x3-1440x2160.png`
  - Arte de caja 1:1 → `logos\caja-1x1-2160.png`
  - Icono de la app 1:1 (300×300), si lo pide → `logos\icono-1x1-300.png`
- **Términos de búsqueda:** los 7 del archivo.
- **Información de copyright y marca comercial**, **Desarrollado por** y **Requisitos adicionales del sistema:** los del final de cada archivo.
- Tráileres: ninguno.

## 6. Opciones de envío

- **Opciones de publicación:** «Publicar este envío en cuanto supere la certificación».
- **Notas para la certificación** (copiar):

```
Pliegue is a free, open-source (AGPL-3.0) offline PDF toolbox. No account or sign-in is needed. Every tool works offline on local files; the only network use is "HTML a PDF" (HTML to PDF) when the user enters a web address. The interface is in Spanish.
Quick test: open "Unir PDF" (Merge PDF), add two PDFs and click the red button; or open "Editar PDF" (Edit PDF), double-click a line of text, type and press Enter.
Bundled helper programs (Poppler, Tesseract OCR, WeasyPrint) run from the package folder. Source code: https://github.com/Blureckzhyto/pliegue
```

- **Capacidades restringidas → justificación de `runFullTrust`** (copiar):

```
Pliegue is a classic Win32 desktop application (Python/Tk) packaged with the Desktop Bridge. runFullTrust is required to run it as a desktop app and to start its bundled command-line helpers (Poppler for page rendering, Tesseract for OCR, WeasyPrint for HTML to PDF) from the package folder. The app does not install services or drivers and keeps its data in its package data folder.
```
