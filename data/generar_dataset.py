
import os
import json
import glob
import time
import google.generativeai as genai
from pypdf import PdfReader
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configurar API Key
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    print("Error: GEMINI_API_KEY no encontrada en .env")
    print("Por favor crea un archivo .env con GEMINI_API_KEY=api_key")
    exit(1)

genai.configure(api_key=API_KEY)

# Configuración del modelo
generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_mime_type": "application/json",
}

model = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    generation_config=generation_config,
    system_instruction="""
    Eres un experto creando datasets de alta calidad para fine-tuning de modelos LLM de atención al cliente y soporte normativo.
    Tu tarea es analizar el texto proporcionado (extraído de un documento) y convertirlo en conocimiento explícito mediante pares de preguntas y respuestas.
    Debes generar una lista de objetos JSON. Cada objeto debe tener EXACTAMENTE esta estructura: 
    {
        "instruction": "Responde como un asesor de atención al cliente, de forma clara, profesional y orientada a resolver la consulta.",
        "input": "La pregunta o consulta derivada del texto.",
        "output": "La respuesta precisa y profesional basada SOLO en el texto proporcionado."
    }

    REGLAS OBLIGATORIAS:
    1. La respuesta (output) debe contener la información FINAL.
        NO utilices frases como:
        - “consulte la documentación”
        - “revise la normativa”
        - “según el manual”
        - “de acuerdo al documento”
        - “puede encontrar más información”
    2. No menciones documentos, páginas, manuales, portales, enlaces ni fuentes externas.
    3. Si el texto NO indica claramente la respuesta, NO generes el par de pregunta y respuesta.
    4. Nunca redactes respuestas genéricas o evasivas.
    5. Si el texto describe pasos, requisitos, estados o reglas, debes expresarlos explícitamente.
    6. No inventes información que no esté presente en el texto.
    7. Si no se puede construir una respuesta concreta, devuelve: []
    8. Devuelve únicamente un JSON válido (array), sin texto adicional.
    """
)

def procesar_pagina(texto_pagina):
    try:
        response = model.generate_content(texto_pagina)
        return json.loads(response.text)
    except Exception as e:
        print(f"Error procesando texto con Gemini: {e}")
        return []

def main():
    docs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "docs")
    if not os.path.exists(docs_dir):
        # Fallback si se ejecuta desde root
        docs_dir = "docs"
    
    if not os.path.exists(docs_dir):
         print(f"No se encuentra el directorio docs en: {docs_dir}")
         return

    pdf_files = glob.glob(os.path.join(docs_dir, "*.pdf"))
    output_file = "dataset_finetuning.jsonl"
    
    print(f"Encontrados {len(pdf_files)} archivos PDF en {docs_dir}")
    
    total_pairs = 0
    
    mode = 'a' if os.path.exists(output_file) else 'w'
    
    for pdf_path in pdf_files:
        print(f"\nProcesando: {os.path.basename(pdf_path)}...")
        try:
            reader = PdfReader(pdf_path)
            for i, page in enumerate(reader.pages):
                texto = page.extract_text()
                if not texto or len(texto.strip()) < 50:
                    continue
                
                print(f"  - Página {i+1}...", end="", flush=True)
                
                pairs = procesar_pagina(texto)
                
                if pairs:
                    print(f" {len(pairs)} pares extraídos.")
                    with open(output_file, "a", encoding="utf-8") as f:
                        for pair in pairs:
                            # Asegurar estructura
                            if "instruction" in pair and "input" in pair and "output" in pair:
                                json.dump(pair, f, ensure_ascii=False)
                                f.write("\n")
                                total_pairs += 1
                else:
                    print(" Ningún par útil.")
                
                time.sleep(1) 
                
        except Exception as e:
            print(f"Error leyendo archivo {pdf_path}: {e}")

    print(f"\n[PROCESO COMPLETADO]")
    print(f"Total de pares generados: {total_pairs}")
    print(f"Dataset guardado en: {output_file}")

if __name__ == "__main__":
    main()
