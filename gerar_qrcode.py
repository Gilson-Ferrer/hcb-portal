import qrcode

data = "https://forms.gle/vFV729JALbTi5iA46"
nome_arquivo = "meu_qrcode.png"

qr = qrcode.QRCode(
    version=1, 
    error_correction=qrcode.constants.ERROR_CORRECT_L, 
    box_size=10, 
    border=4, 
)

qr.add_data(data)
qr.make(fit=True)

img = qr.make_image(fill_color="black", back_color="white")


img.save(nome_arquivo)

print(f"QR Code gerado com sucesso e salvo como: {nome_arquivo}")