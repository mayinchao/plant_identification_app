import sys
import os
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import aiofiles
from datetime import datetime
import asyncio
from contextlib import asynccontextmanager

# 修复导入路径 - 在导入模型之前设置路径
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from models.plant_model import PlantRecognitionModel

    print("✅ 植物识别模型导入成功")
except ImportError as e:
    print(f"❌ 模型导入失败: {e}")
    PlantRecognitionModel = None

print(" 启动青芜识界后端服务...")

# 全局变量
plant_model = None
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """生命周期管理 - 替换已弃用的 on_event"""
    # 启动时加载模型
    global plant_model
    try:
        # 使用您的真实模型权重路径
        model_path = "models/weights/epoch_35_best.pth"

        # 确保路径正确
        if not os.path.isabs(model_path):
            model_path = os.path.join(current_dir, model_path)

        print(f"🔍 检查模型文件: {model_path}")
        print(f"📁 文件是否存在: {os.path.exists(model_path)}")

        if not os.path.exists(model_path):
            print("⚠️  模型文件不存在，使用演示模式")
            plant_model = None
        else:
            # 根据您的训练数据设置正确的类别数
            num_classes = 44  # 修改为您的实际训练类别数

            plant_model = PlantRecognitionModel(
                model_path=model_path,
                num_classes=num_classes
            )
            print("🎉 真实植物识别模型加载成功！")
            print("💡 模式: 真实AI识别模式")

    except Exception as e:
        print(f"❌ 模型加载失败: {e}")
        import traceback
        traceback.print_exc()  # 打印详细错误信息
        plant_model = None
        print("⚠️  回退到演示模式")

    print("🌐 API服务启动中...")
    print("📚 API文档: http://localhost:8001/docs")
    yield
    # 关闭时清理资源
    print("🔴 服务关闭中...")


# 初始化应用
app = FastAPI(
    title="青芜识界植物识别API",
    description="智能植物识别后端服务",
    version="1.0.0",
    lifespan=lifespan
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    mode = "真实AI识别模式" if plant_model else "演示模式"
    return {
        "message": "欢迎使用青芜识界植物识别API",
        "status": "服务运行中",
        "mode": mode,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/health")
async def health_check():
    """健康检查"""
    mode = "真实AI识别模式" if plant_model else "演示模式"
    return {
        "status": "healthy",
        "mode": mode,
        "model_loaded": plant_model is not None,
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/identify")
async def identify_plant(file: UploadFile = File(...)):
    """植物识别端点"""
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

        print(f" 处理图片: {file.filename}")

        # 如果有真实模型，使用真实识别
        if plant_model:
            try:
                # 使用真实模型进行识别
                result = plant_model.predict(file_path)

                # 清理临时文件
                os.remove(file_path)

                return {
                    "success": True,
                    "identification": result,
                    "message": f"AI识别成功 - {result['top_prediction']['name']}",
                    "demo_mode": False,
                    "timestamp": datetime.now().isoformat()
                }
            except Exception as model_error:
                print(f"🤖 模型识别失败，回退到演示模式: {model_error}")
                # 继续执行演示模式

        # 演示模式
        await asyncio.sleep(1)

        # 演示结果
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

        # 清理临时文件
        os.remove(file_path)

        return {
            "success": True,
            "identification": {
                "top_prediction": demo_plants[0],
                "all_predictions": demo_plants
            },
            "message": f"演示模式: 识别成功 - {demo_plants[0]['name']}",
            "demo_mode": True,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        print(f" 识别过程出错: {e}")
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

    # 尝试不同的端口
    port = 8001
    max_attempts = 5

    for attempt in range(max_attempts):
        try:
            uvicorn.run(
                app,
                host="0.0.0.0",
                port=port,
                log_level="info"
            )
            break
        except OSError as e:
            if "address already in use" in str(e) or "10048" in str(e):
                print(f"⚠️  端口 {port} 被占用，尝试端口 {port + 1}")
                port += 1
            else:
                raise e
    else:
        print(f"❌ 无法找到可用端口，尝试了 {max_attempts} 次")