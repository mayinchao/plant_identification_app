from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "青芜识界后端服务运行成功！", "status": "OK"}

@app.post("/api/identify")
async def identify_plant(file: UploadFile = File(...)):
    return {
        "success": True,
        "message": "演示模式：识别功能正常",
        "identification": {
            "top_prediction": {
                "name": "龟背竹",
                "sci_name": "Monstera deliciosa",
                "family": "天南星科",
                "confidence": 0.85
            }
        }
    }

if __name__ == "__main__":
    print(" 启动青芜识界测试服务器...")
    print(" 访问: http://localhost:8000")
    print(" 文档: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)
