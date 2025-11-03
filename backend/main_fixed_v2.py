import sys
import os
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import aiofiles
from datetime import datetime
import asyncio

print("🚀 启动青芜识界后端服务...")

# 修复导入路径
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 尝试导入模型
try:
    from models.plant_model import PlantRecognitionModel

    MODEL_AVAILABLE = True
    print("✅ 植物识别模型导入成功")
except ImportError as e:
    print(f"❌ 模型导入失败: {e}")
    MODEL_AVAILABLE = False
    PlantRecognitionModel = None

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
    if MODEL_AVAILABLE:
        try:
            # 检查模型文件
            model_path = "models/weights/epoch_35_best.pth"
            full_model_path = os.path.join(current_dir, model_path)

            print(f"🔍 检查模型文件: {full_model_path}")
            print(f"📁 文件是否存在: {os.path.exists(full_model_path)}")

            plant_model = PlantRecognitionModel(
                model_path=full_model_path,
                num_classes=5  # 根据您的类别数调整
            )

            if hasattr(plant_model, 'model_loaded') and plant_model.model_loaded:
                print("🎉 真实植物识别模型加载成功！")
                print("💡 模式: 真实AI识别模式")
            else:
                print("⚠️  模型使用随机权重，识别结果为演示数据")
                print("💡 模式: 演示模式")

        except Exception as e:
            print(f"❌ 模型加载失败: {e}")
            plant_model = None
    else:
        print("❌ 模型组件不可用，API将以演示模式运行")
        plant_model = None

    print("🌐 API服务启动中...")
    print("📚 API文档: http://localhost:8001/docs")


async def demo_identify_plant(file: UploadFile):
    """演示模式：返回模拟识别结果"""
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="请上传图片文件")

    # 模拟处理时间
    await asyncio.sleep(1)

    # 返回模拟结果
    demo_plants = [
        {
            "name": "龟背竹",
            "sci_name": "Monstera deliciosa",
            "family": "天南星科",
            "confidence": 0.85,
            "class_id": 0
        },
        {
            "name": "栀子花",
            "sci_name": "Gardenia jasminoides",
            "family": "茜草科",
            "confidence": 0.12,
            "class_id": 1
        },
        {
            "name": "多肉植物",
            "sci_name": "Succulent plants",
            "family": "多个科属",
            "confidence": 0.03,
            "class_id": 2
        }
    ]

    return {
        "success": True,
        "identification": {
            "top_prediction": demo_plants[0],
            "all_predictions": demo_plants
        },
        "message": "演示模式: 识别成功 (龟背竹)",
        "demo_mode": True,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/")
async def root():
    return {
        "message": "欢迎使用青芜识界植物识别API",
        "status": "服务运行中",
        "model_loaded": plant_model is not None and hasattr(plant_model, 'model_loaded') and plant_model.model_loaded,
        "mode": "真实AI模式" if plant_model and hasattr(plant_model,
                                                        'model_loaded') and plant_model.model_loaded else "演示模式",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "model_loaded": plant_model is not None and hasattr(plant_model, 'model_loaded') and plant_model.model_loaded,
        "mode": "真实AI模式" if plant_model and hasattr(plant_model,
                                                        'model_loaded') and plant_model.model_loaded else "演示模式",
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/identify")
async def identify_plant(file: UploadFile = File(...)):
    """植物识别端点"""
    # 如果模型未加载或加载失败，使用演示模式
    if plant_model is None or not hasattr(plant_model, 'model_loaded') or not plant_model.model_loaded:
        return await demo_identify_plant(file)

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
                "ai_mode": True,
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
        },
        "多肉植物": {
            "name": "多肉植物",
            "sci_name": "Succulent plants",
            "family": "多个科属",
            "distribution": "全球广泛分布",
            "features": "叶片肥厚多汁，用于储存水分",
            "habit": "耐旱性强，喜欢阳光充足的环境",
            "culture": "象征坚韧不拔的生命力",
            "flower_language": "坚韧",
            "care_tips": ["少浇水", "充足光照", "良好排水"]
        },
        "玫瑰": {
            "name": "玫瑰",
            "sci_name": "Rosa rugosa",
            "family": "蔷薇科",
            "distribution": "原产中国，现世界各地广泛栽培",
            "features": "灌木，茎密生锐刺，花瓣倒卵形，重瓣至半重瓣",
            "habit": "喜阳光，耐寒、耐旱，喜排水良好、疏松肥沃的土壤",
            "culture": "象征爱情与美丽",
            "flower_language": "爱情",
            "care_tips": ["充足光照", "适度浇水", "定期修剪"]
        },
        "向日葵": {
            "name": "向日葵",
            "sci_name": "Helianthus annuus",
            "family": "菊科",
            "distribution": "原产北美，现世界各地广泛栽培",
            "features": "一年生草本植物，茎直立，头状花序，花盘随太阳转动",
            "habit": "喜温暖、耐旱，需要充足阳光",
            "culture": "象征忠诚、阳光和活力",
            "flower_language": "沉默的爱",
            "care_tips": ["全日照", "保持土壤湿润", "支撑高大植株"]
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
    print("=" * 50)
    print("   青芜识界 - 植物识别后端服务")
    print("   端口: 8001 (8000端口被占用)")
    print("=" * 50)
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,  # 使用8001端口
        log_level="info"
    )