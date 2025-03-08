import qrcode
import os

# Definir la ruta del menú PDF en la carpeta static
STATIC_DIR = os.path.join(os.getcwd(), "static")
MENU_PDF_PATH = os.path.join(STATIC_DIR, "menu.pdf")
QR_CODE_PATH = os.path.join(STATIC_DIR, "qr_menu.png")

# Verificar si el archivo PDF existe
if not os.path.exists(MENU_PDF_PATH):
    print("❌ Error: El archivo 'menu.pdf' no se encuentra en la carpeta 'static/'.")
    print("➡️ Mueve el archivo con: mv carta_menu.pdf static/menu.pdf")
    exit()

# URL donde el PDF será accesible
menu_pdf_url = "http://localhost:8000/static/menu.pdf"

# Generar el QR Code
qr = qrcode.QRCode(
    version=1,
    error_correction=qrcode.constants.ERROR_CORRECT_L,
    box_size=10,
    border=4,
)
qr.add_data(menu_pdf_url)
qr.make(fit=True)

# Guardar la imagen QR en la carpeta 'static/'
img = qr.make_image(fill="black", back_color="white")
img.save(QR_CODE_PATH)

print("✅ QR generado correctamente en 'static/qr_menu.png'")
print(f"🔗 Escanéalo para abrir: {menu_pdf_url}")

