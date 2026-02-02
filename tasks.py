from pathlib import Path

from robocorp import browser
from robocorp.tasks import task
from RPA.PDF import PDF
import os
from datetime import datetime

usuario_penotariado = os.environ.get("USUARIO_PENOTARIADO")
pass_penotariado = os.environ.get("PASS_PENOTARIADO")
usuario_catastro = os.environ.get("USUARIO_CATASTRO")
soporte_catastro = os.environ.get("SOPORTE_CATASTRO")

date_today = datetime.now().strftime("%d/%m/%Y")
catastro_id = "9734606DF1993S0056YQ"
codigo_postal = "08191"

print(f"Today's date: {date_today}")
print(f"Catastro ID: {catastro_id}")
print(f"Codigo Postal: {codigo_postal}")

@task
def index():
    """
    Main task which solves the RPA challenge!

    Downloads the source data Excel file and uses Playwright to fill the entries inside
    rpachallenge.com.
    """
    browser.configure(
        browser_engine="chromium",
        screenshot="only-on-failure"
    )
    try:
        # Catastro website automation
        login_catastro()
        data_catastro = search_catastral_data()

        # Penotariado website automation
        login_penotariado()
        go_to_maps()
        data_penotariado = extract_statistics()

        print(f"Data from Catastro: {data_catastro}")
        print(f"Data from Penotariado: {data_penotariado}")

    finally:
        print("Automation finished!")
        return data_catastro, data_penotariado

# Catastro
def login_catastro():
    """
    Login to the site with given credentials.
    """
    browser.goto("https://www.sedecatastro.gob.es/Accesos/SECAccDNI.aspx?Dest=3&ejercicio=2026")
    page = page = browser.page()
    page.wait_for_load_state("networkidle")

    page.fill('#ctl00_Contenido_nif', f"{usuario_catastro}")
    page.fill('#ctl00_Contenido_soporte', f"{soporte_catastro}")
    page.click('text=Validar DNI / Soporte')

def search_catastral_data():
    """
    Search for cadastral data using a given reference.
    """
    page = browser.page()
    page.wait_for_load_state("networkidle")

    page.select_option('#ctl00_Contenido_ddlFinalidad', "Efectos informativos")
    page.fill('#ctl00_Contenido_txtFechaConsulta', f"{date_today}")
    page.fill('#ctl00_Contenido_txtRC2', f"{catastro_id}")
    page.click('#ctl00_Contenido_btnValorReferencia')

    data = export_data(page)
    return data

def export_data(page):
    """
    Extract cadastral data from the results page and save it to a file.
    """

    result_table = page.inner_text('#ctl00_Contenido_tblInmueble')
    print(result_table)

    lines = result_table.splitlines()

    data = {
        "referencia_catastral": lines[1].strip(),
        "localizacion": f"{lines[3].strip()}, {lines[4].strip()}",
        "clase": lines[6].strip(),
        "uso_principal": lines[8].strip(),
        "fecha_valor": lines[10].strip(),
        "valor_referencia": lines[12].strip(),
    }

    return data

# Penotariado 
def login_penotariado():
    """
    Login to the Penotariado site with given credentials.
    """
    browser.goto("https://penotariado.com/inmobiliario/home")
    page = browser.page()
    page.wait_for_load_state("networkidle")
    page.click('text=Login')

    page = browser.page()
    page.fill('#username', f"{usuario_penotariado}")
    page.fill('input[name="password"]', f"{pass_penotariado}")
    page.click('#login')
    page.wait_for_url("**/home**", timeout=15000)

def go_to_maps():
    """
    Search for specific data on the Penotariado site.
    """
    page = browser.page()
    page.click('text=Mapa')
    page = browser.page()
    page.wait_for_load_state("networkidle")
    page.click('text=Descartar todas')

    # Search codigo postal
    page = browser.page()
    search_details_codigo_postal(page)

def search_details_codigo_postal(page):
    """
    Search for details using codigo postal.
    """   
    # Debug: print all frames
    print(page.frames)

    # Try iframe context
    # Get the map frame
    map_frame = page.frame(url="https://penotariado.com/mapa/?locale=es")
    
    # Fill input in that frame
    map_frame.fill('input[placeholder="Buscar provincia, municipio o código postal"]', f"{codigo_postal}")
    map_frame.click('button[aria-label="Buscar"]')
    page.wait_for_load_state("networkidle")

    map_frame.wait_for_selector('button.btn-statistics', state="visible", timeout=15000)
    map_frame.click('button.btn-statistics')
    page.wait_for_load_state("networkidle")

    page = browser.page()
    page.locator('button.c-ctn-button--primary:has-text("Continuar")').click()

def extract_statistics():
    page = browser.page()
    page.wait_for_load_state("networkidle")
    datos = {
        "periodo": page.locator('section.c-pin-statistics__indicators h3').inner_text(),
        "precio_medio_m2": page.locator('dt:has-text("Precio medio m²") + dd').inner_text(),
        "compraventas": page.locator('dt:has-text("Compraventas") + dd').inner_text(),
        "importe_medio": page.locator('dt:has-text("Importe medio") + dd').inner_text(),
        "superficie_media": page.locator('dt:has-text("Superficie media") + dd').inner_text()
    }

    return datos

