
import json
from robocorp import browser
from robocorp.tasks import task
from RPA.PDF import PDF
from datetime import datetime
from RPA.Robocorp.Vault import Vault
from robocorp import workitems

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

    # Get today's date
    date_today = datetime.now().strftime("%d/%m/%Y")

    # Get inputs from workitem
    wi = workitems.inputs.current
    raw = wi.payload

    # Si viene como string JSON:
    if isinstance(raw, str):
        payload = json.loads(raw)
    else:
        payload = raw or {}

    catastro_id = payload["catastro_id"]
    supabase_id = payload["supabase_id"]

    print("OK:", catastro_id, supabase_id)

    print(f"Today's date: {date_today}")
    print(f"Catastro ID: {catastro_id}")

    # Get credentials from Vault
    vault = Vault()
    cred = vault.get_secret("valorix")
    usuario_catastro = cred["USUARIO_CATASTRO"]
    soporte_catastro = cred["SOPORTE_CATASTRO"]

    print("Starting automation...")

    try:
        # Catastro website automation
        login_catastro(usuario_catastro, soporte_catastro)
        data_catastro = search_catastral_data(date_today, catastro_id)
        
        workitems.outputs.create(
            payload={
                "status": "success",
                "data_catastro": data_catastro, 
                "supabase_id": supabase_id
            }
        )
    except Exception as e:
        print(f"An error occurred: {e}")
        raise e
    finally:
        print("Automation finished!")
        data_catastro = data_catastro if data_catastro else {}
    
    return data_catastro

# Catastro
def login_catastro(usuario_catastro, soporte_catastro):
    """
    Login to the site with given credentials.
    """
    browser.goto("https://www.sedecatastro.gob.es/Accesos/SECAccDNI.aspx?Dest=3&ejercicio=2026")
    page = page = browser.page()
    page.wait_for_load_state("networkidle")

    page.fill('#ctl00_Contenido_nif', f"{usuario_catastro}")
    page.fill('#ctl00_Contenido_soporte', f"{soporte_catastro}")
    page.click('text=Validar DNI / Soporte')

def search_catastral_data(date_today, catastro_id):
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