from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import aiofiles
import os
from datetime import datetime

from backend.models.plant_model import PlantRecognitionModel

# 初始化应用
app = FastAPI(
    title="青芜识界植物识别API",
    description="基于 BryoFormer 的智能植物识别后端服务",
    version="1.0.0"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局变量
plant_model = None
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.on_event("startup")
async def startup_event():
    """启动时加载模型"""
    global plant_model
    try:
        plant_model = PlantRecognitionModel(
            model_path="models/weights/best_plant_model.pth",
            num_classes=44
        )
        print("🎉 植物识别模型加载成功！")
        print("🌐 API服务已启动: http://localhost:8000")
        print("📚 API文档: http://localhost:8000/docs")
    except Exception as e:
        print(f"❌ 模型加载失败: {e}")
        plant_model = None


@app.get("/")
async def root():
    return {
        "message": "欢迎使用青芜识界植物识别API",
        "status": "服务运行中",
        "model_loaded": plant_model is not None,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "model_loaded": plant_model is not None,
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/identify")
async def identify_plant(file: UploadFile = File(...)):
    """植物识别端点"""
    if plant_model is None:
        raise HTTPException(status_code=503, detail="模型未加载，请检查服务状态")

    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="请上传图片文件 (JPEG, PNG等)")

    try:
        # 保存上传的文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_extension = os.path.splitext(file.filename)[1]
        file_path = os.path.join(UPLOAD_DIR, f"temp_{timestamp}{file_extension}")

        async with aiofiles.open(file_path, 'wb') as buffer:
            content = await file.read()
            await buffer.write(content)

        print(f"📸 处理图片: {file.filename}")

        # 调用模型识别
        result = await plant_model.predict(file_path)

        # 清理临时文件
        os.remove(file_path)

        if result["success"] and result["predictions"]:
            top_plant = result["top_prediction"]
            print(f"✅ 识别成功: {top_plant['name']} (置信度: {top_plant['confidence']:.2%})")

            return {
                "success": True,
                "identification": {
                    "top_prediction": top_plant,
                    "all_predictions": result["predictions"]
                },
                "message": f"识别成功: {top_plant['name']}",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "success": False,
                "message": "识别失败，请尝试其他图片",
                "error": result.get("error", "未知错误")
            }

    except Exception as e:
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        print(f"❌ 识别过程出错: {e}")
        raise HTTPException(status_code=500, detail=f"识别过程出错: {str(e)}")


@app.get("/api/plants/{plant_name}")
async def get_plant_details(plant_name: str):
    """获取植物详细信息"""
    if plant_model is None:
        raise HTTPException(status_code=503, detail="模型未加载")

    # 这里可以扩展为从数据库获取详细信息
    plant_database = {
        "龟背竹": {
            "name": "龟背竹",
            "sci_name": "Monstera deliciosa",
            "family": "天南星科 龟背竹属",
            "distribution": "原产墨西哥，现全球热带地区广泛栽培",
            "features": "茎干粗壮，节间短；叶片大，轮廓心状卵形，羽状分裂，革质，表面发亮",
            "habit": "喜温暖湿润环境，忌强光暴晒和干燥，耐阴",
            "culture": "叶片形态独特，酷似龟背，象征「健康长寿」",
            "flower_language": "健康长寿",
            "care_tips": ["喜半阴环境", "保持土壤湿润", "定期施肥"]
        },
        "栀子花": {
            "name": "栀子花",
            "sci_name": "Gardenia jasminoides",
            "family": "茜草科 栀子属",
            "distribution": "原产中国，现世界各地广泛栽培",
            "features": "常绿灌木，高0.3-3米；嫩枝常被短毛，枝圆柱形，灰色",
            "habit": "喜温暖湿润气候，好阳光但又不能经受强烈阳光照射",
            "culture": "象征吉祥如意、祥符瑞气",
            "flower_language": "永恒的爱与约定",
            "care_tips": ["酸性土壤", "充足光照", "保持湿润"]
        }
    }

    if plant_name in plant_database:
        return {
            "success": True,
            "plant": plant_database[plant_name]
        }
    else:
        return {
            "success": False,
            "message": f"未找到植物 '{plant_name}' 的详细信息"
        }


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )