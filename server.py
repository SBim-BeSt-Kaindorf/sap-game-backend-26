from flask import Flask, request, jsonify
from escpos.printer import Dummy
import qrcode
import win32print
from PIL import Image, ImageDraw, ImageFont
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
PORT = 3001
multiplier = 48

def create_big_text(text, font_size):
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except IOError:
        font = ImageFont.load_default()
    width = 512  # Belegbreite in Pixel

    img = Image.new('1', (width, font_size + 20), color=1)  # weiß
    draw = ImageDraw.Draw(img)

    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]

    draw.text(((width - text_width) // 2, 0), text, font=font, fill=0)  # schwarz=0
    return img

def create_receipt_bytes(data, qr_url="https://www.htl-kaindorf.at/"):
    printer = Dummy()

    employee_name = data.get("employeeName", "Gast-Manager")
    customer = data.get("customerName", "Kunde")
    order_number = data.get("orderNumber", "AUF-4711")
    invoice_number = data.get("invoiceNumber", "RE-90004711")
    items = data.get("items", [])
    discount_percent = data.get("discountPercent", 0)
    discount_amount = data.get("discountAmount", 0.0)
    tax_amount = data.get("taxAmount", 0.0)
    grand_total = data.get("grandTotal", 0.0)
    duration_seconds = data.get("durationSeconds", 0)
    satisfaction = data.get("satisfactionScore", 100)
    rank_title = data.get("rankTitle", "Junior SAP Explorer")

    # Header
    printer.set(align='center', bold=True)
    printer.image(create_big_text("SAP BELEG", 60), impl='bitImageRaster')
    printer.text("HTL Kaindorf GmbH - Vertiefung SAP\n")
    printer.text("-" * multiplier + "\n")

    # Prozessdaten
    printer.set(align='left', bold=False)
    printer.text(f"Sachbearbeiter: {employee_name}\n")
    printer.text(f"Kunde:          {customer}\n")
    printer.text(f"Auftrag / Re.:  {order_number} / {invoice_number}\n")
    printer.text("-" * multiplier + "\n\n")

    # Artikeltabelle
    printer.text("Artikel               | Menge |            Preis\n")
    printer.text("-" * 22 + "+" + "-" * 7 + "+" + "-" * 17 + "\n")

    for p in items:
        name = str(p.get('name', 'Artikel'))[:22].ljust(22)
        qty_val = p.get('quantity', 1)
        unit_price = p.get('unitPrice', 0.0)
        total_line = p.get('totalPrice', unit_price * qty_val)

        qty = f"x{qty_val} ".rjust(7)
        price = f"{total_line:.2f} EUR".rjust(17)
        printer.text(f"{name}|{qty}|{price}\n")

    if discount_percent > 0:
        disc_label = f"Rabatt (-{discount_percent}%)".ljust(22)
        disc_qty = " ".rjust(7)
        disc_val = f"-{discount_amount:.2f} EUR".rjust(17)
        printer.text(f"{disc_label}|{disc_qty}|{disc_val}\n")

    printer.text("-" * multiplier + "\n")

    # Steuer & Gesamt
    tax_text = f"{tax_amount:.2f} EUR".rjust(34)
    printer.text("inkl. 20% USt:" + tax_text + "\n")

    printer.set(bold=True)
    price_text = f"{grand_total:.2f} EUR".rjust(41)
    printer.text("Gesamt:" + price_text + "\n")
    printer.set(bold=False)
    printer.text("-" * multiplier + "\n\n")

    # Gamification / Highscore Box
    printer.set(align="center", bold=True)
    printer.text("*** DEINE SAP-PERFORMANCE ***\n")
    printer.set(bold=False)
    printer.text(f"Zeit: {duration_seconds} Sek. | Kundenzufriedenheit: {satisfaction}%\n")
    printer.set(bold=True)
    # Emojis für den Thermodrucker herausfiltern
    clean_rank = rank_title.encode("ascii", "ignore").decode("ascii").strip()
    printer.text(f"Rang: {clean_rank}\n\n")
    printer.set(bold=False)

    # QR-Code
    printer.set(align='center')
    qr_img = qrcode.make(qr_url).convert("1")
    printer.image(qr_img, impl='bitImageRaster')
    printer.text("\n")

    printer.image(create_big_text("HTL Kaindorf", 48), impl='bitImageRaster')
    printer.image(create_big_text("Informatik & SAP", 30), impl='bitImageRaster')

    # Footer
    printer.set(align="left")
    printer.text("\nNeugierig auf Wirtschaft & IT?\n")
    printer.text("Scanne den QR-Code für alle Infos zu unserer\n")
    printer.text("Ausbildung und dem Tag der offenen Tür!\n\n")

    printer.cut()
    return printer.output

def print_raw_bytes(printer_name, data_bytes):
    try:
        hPrinter = win32print.OpenPrinter(printer_name)
        win32print.StartDocPrinter(hPrinter, 1, ("Bondrucker", None, "RAW"))
        win32print.StartPagePrinter(hPrinter)
        win32print.WritePrinter(hPrinter, data_bytes)
        win32print.EndPagePrinter(hPrinter)
        win32print.EndDocPrinter(hPrinter)
        win32print.ClosePrinter(hPrinter)
        print("Druck erfolgreich")
    except Exception as e:
        print("Fehler beim Drucken:", e)
        raise

@app.route("/print", methods=["POST"])
def print_receipt():
    data = request.json or {}
    try:
        receipt_bytes = create_receipt_bytes(data, qr_url="https://www.htl-kaindorf.at/")
        printer_name = "POS-80C"
        print_raw_bytes(printer_name, receipt_bytes)
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)