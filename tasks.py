
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
    codigo_postal = payload["codigo_postal"]

    print("OK:", catastro_id, codigo_postal)

    print(f"Today's date: {date_today}")
    print(f"Catastro ID: {catastro_id}")
    print(f"Codigo Postal: {codigo_postal}")

    # Get credentials from Vault
    vault = Vault()
    cred = vault.get_secret("valorix")
    usuario_penotariado = cred["USUARIO_PENOTARIADO"]
    pass_penotariado = cred["PASS_PENOTARIADO"]
    usuario_catastro = cred["USUARIO_CATASTRO"]
    soporte_catastro = cred["SOPORTE_CATASTRO"]

    print("Starting automation...")
    print("Logging user Penotariado:", usuario_penotariado)

    try:
        # Catastro website automation
        login_catastro(usuario_catastro, soporte_catastro)
        data_catastro = search_catastral_data(date_today, catastro_id)

        # Penotariado website automation
        login_penotariado(usuario_penotariado, pass_penotariado)
        go_to_maps(codigo_postal)
        data_penotariado = extract_statistics()

    except Exception as e:
        print(f"An error occurred: {e}")
        raise e
    finally:
        print("Automation finished!")
        data_catastro = data_catastro if data_catastro else {}
        data_penotariado = data_penotariado if data_penotariado else {}
    
    # Crear work item de salida con éxito
    outputs = workitems.outputs.create({
        "status": "success",
        "data_catastro": data_catastro,
        "data_penotariado": data_penotariado
    })
    outputs.save()
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

# Penotariado 
def login_penotariado(usuario_penotariado, pass_penotariado):
    """
    Login to the Penotariado site with given credentials.
    """
    print("=== INICIO LOGIN PENOTARIADO ===")
    browser.goto("https://penotariado.com/inmobiliario/home")
    page = browser.page()
    page.wait_for_load_state("networkidle")
    
    print(f"URL actual tras goto: {page.url}")
    print(f"Título página: {page.title()}")
    
    # Verificar si está bloqueado
    page_content = page.content().lower()
    if "blocked" in page_content or "event_id" in page_content or "captcha" in page_content:
        print("❌ PÁGINA BLOQUEADA DETECTADA")
        page.screenshot(path="output/blocked_login.png")
        print(f"HTML snippet: {page.content()[:500]}")
        raise Exception("Sitio bloqueado por anti-bot")
    
    print("Buscando botón 'Login'...")
    page.click('text=Login', timeout=10000)
    
    print(f"URL tras click Login: {page.url}")
    
    # NO volver a llamar browser.page() - usar la misma referencia
    page.wait_for_selector('#username', state="visible", timeout=30000)
    print(f"URL con formulario visible: {page.url}")
    
    page.fill('#username', usuario_penotariado)
    page.fill('input[name="password"]', pass_penotariado)
    page.click('#login')
    
    page.wait_for_url("**/home**", timeout=15000)
    print(f"✓ Login exitoso. URL final: {page.url}")
    print("=== FIN LOGIN PENOTARIADO ===\n")


def go_to_maps(codigo_postal):
    """
    Search for specific data on the Penotariado site.
    """
    print("=== INICIO GO_TO_MAPS ===")
    page = browser.page()
    print(f"URL inicial go_to_maps: {page.url}")
    
    page.click('text=Map')
    page.wait_for_load_state("networkidle")
    print(f"URL tras click Map: {page.url}")
    
    page.click('text=Descartar todas')
    print(f"URL tras descartar cookies: {page.url}")
    
    # NO volver a llamar browser.page()
    search_details_codigo_postal(page, codigo_postal)
    print("=== FIN GO_TO_MAPS ===\n")


def search_details_codigo_postal(page, codigo_postal):
    """
    Search for details using codigo postal.
    """
    print("=== INICIO SEARCH_DETAILS ===")
    print(f"URL al entrar: {page.url}")
    print(f"Número de frames: {len(page.frames)}")
    
    # Debug frames
    for i, frame in enumerate(page.frames):
        print(f"Frame {i}: {frame.url}")
    
    # Get the map frame
    map_frame = None
    for frame in page.frames:
        if "penotariado.com/mapa" in frame.url:
            map_frame = frame
            print(f"✓ Map frame encontrado: {frame.url}")
            break
    
    if not map_frame:
        print("❌ ERROR: No se encontró iframe del mapa")
        print("Frames disponibles:")
        for frame in page.frames:
            print(f"  - {frame.url}")
        page.screenshot(path="output/no_map_frame.png")
        raise Exception("No se encontró el iframe del mapa")
    
    # Fill input in that frame
    print(f"Buscando codigo postal: {codigo_postal}")
    map_frame.fill('input[placeholder="Buscar provincia, municipio o código postal"]', codigo_postal)
    map_frame.click('button[aria-label="Buscar"]')
    page.wait_for_load_state("networkidle")
    print(f"URL tras búsqueda: {page.url}")
    
    print("Esperando botón estadísticas...")
    map_frame.wait_for_selector('button.btn-statistics', state="visible", timeout=15000)
    map_frame.click('button.btn-statistics')
    page.wait_for_load_state("networkidle")
    print(f"URL tras click estadísticas: {page.url}")
    
    # NO volver a llamar browser.page()
    print("Buscando botón Continuar...")
    page.locator('button.c-ctn-button--primary:has-text("Continuar")').click()
    print(f"URL tras click Continuar: {page.url}")
    print("=== FIN SEARCH_DETAILS ===\n")


def extract_statistics():
    print("=== INICIO EXTRACT_STATISTICS ===")
    page = browser.page()
    page.wait_for_load_state("networkidle")
    print(f"URL al extraer estadísticas: {page.url}")
    
    # Verificar que estamos en la página correcta
    if "penotariado.com" not in page.url:
        print(f"❌ ERROR: URL incorrecta: {page.url}")
        page.screenshot(path="output/wrong_url_statistics.png")
        raise Exception(f"URL incorrecta al extraer estadísticas: {page.url}")
    
    print("Esperando selector estadísticas...")
    try:
        page.wait_for_selector('section.c-pin-statistics__indicators h3', state="visible", timeout=10000)
    except Exception as e:
        print(f"❌ ERROR: No se encontró selector de estadísticas")
        print(f"URL actual: {page.url}")
        print(f"Título: {page.title()}")
        page.screenshot(path="output/no_statistics_selector.png")
        raise e
    
    print("Extrayendo datos...")
    datos = {
        "periodo": page.locator('section.c-pin-statistics__indicators h3').inner_text(),
        "precio_medio_m2": page.locator('dt:has-text("Precio medio m²") + dd').inner_text(),
        "compraventas": page.locator('dt:has-text("Compraventas") + dd').inner_text(),
        "importe_medio": page.locator('dt:has-text("Importe medio") + dd').inner_text(),
        "superficie_media": page.locator('dt:has-text("Superficie media") + dd').inner_text()
    }
    print(f"✓ Datos extraídos: {datos}")
    print("=== FIN EXTRACT_STATISTICS ===\n")
    return datos