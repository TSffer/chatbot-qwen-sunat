from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from unsloth import FastLanguageModel
from qwen_tts import Qwen3TTSModel
import torch
import uvicorn
import os
import uuid
import soundfile as sf

# CONFIGURACIÓN
ADAPTER_PATH = "/content/drive/My Drive/Modelos_Qwen/Sunat_LoRA_v1"
SPEAKER_WAV = "/content/referencia_peru.wav"
TEXT_REF = 'Tocar el xilófono es mi hobby favorito.'

# CARGA DEL MODELO LLM
print("Cargando modelo finatuning SUNAT....")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = ADAPTER_PATH,
    max_seq_length = 2048,
    dtype = None,
    load_in_4bit = True,
)
FastLanguageModel.for_inference(model)
print("Modelo SUNAT cargado exitosamente.")

# PLANTILLA ALPACA
alpaca_prompt = """A continuación hay una instrucción que describe una tarea, junto con una entrada que proporciona más contexto. Escribe una respuesta que complete apropiadamente la solicitud.

### Instrucción:
{}

### Entrada:
{}

### Respuesta:
{}"""


# CARGA DEL MODELO AUDIO
print("Cargando Tu Modelo TTS del curso...")
DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"
DTYPE = torch.bfloat16 if torch.cuda.is_available() else torch.float32

model_tts = Qwen3TTSModel.from_pretrained(
    "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
    device_map=DEVICE,
    dtype=DTYPE,
)
print("Modelo Base cargado")

class Consulta(BaseModel):
    pregunta: str
    temperatura: float = 0.3
    max_tokens: int = 512

# Inicializar FastAPI
app = FastAPI(title="API Chatbot SUNAT")

def procesar_consulta_llm(pregunta, max_tokens, temperatura):
    instruccion = "Responde como un asesor de atención al cliente de la SUNAT, de forma clara, profesional y orientada a resolver la consulta."
    prompt = alpaca_prompt.format(instruccion, pregunta, "")
    inputs = tokenizer([prompt], return_tensors = "pt").to("cuda")

    outputs = model.generate(
        **inputs,
        max_new_tokens = max_tokens,
        temperature = temperatura,
        use_cache = True
    )
    resultado = tokenizer.batch_decode(outputs, skip_special_tokens=True)[0]
    return resultado.split("### Respuesta:")[1].strip() if "### Respuesta:" in resultado else resultado

@app.post("/v1/chat")
async def chat(consulta: Consulta):
    try:
        respuesta = procesar_consulta_llm(consulta.pregunta, consulta.max_tokens, consulta.temperatura)

        return {
            "pregunta": consulta.pregunta,
            "respuesta": respuesta,
            "modelo": "Qwen3-8B-Sunat_LoRA_v1"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/chat/audio")
async def chat_audio(consulta: Consulta):
    try:
        texto = procesar_consulta_llm(consulta.pregunta, consulta.max_tokens, consulta.temperatura)

        wavs, sr = model_tts.generate_voice_clone(
            text=texto,
            language="Auto",
            ref_audio=SPEAKER_WAV,
            ref_text=TEXT_REF
        )

        filename = f"resp_{uuid.uuid4()}.wav"
        sf.write(filename, wavs[0], sr)

        return FileResponse(filename, media_type="audio/wav", filename=filename)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)