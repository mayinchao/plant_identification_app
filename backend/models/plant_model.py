import torch
import torch.nn as nn
from torchvision import transforms
from PIL import Image
import json
import os
from backend.models.bryoFormer import BryoFormer


class PlantRecognitionModel:
    def __init__(self, model_path=None, num_classes=44, device=None):
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.num_classes = num_classes

        print("🚀 初始化植物识别模型...")
        self.model = self.load_model(model_path)
        self.class_names = self.load_class_names()
        self.transform = self.get_transform()
        print("✅ 模型初始化完成")

    def load_model(self, model_path):
        """加载 BryoFormer 模型"""
        model = BryoFormer(
            img_size=224,
            patch_size=16,
            in_chans=3,
            num_classes=self.num_classes,
            embed_dim=384,
            depth=8,
            mlp_ratio=2.
        )

        # 检查模型文件是否存在
        if model_path and os.path.exists(model_path):
            print(f"📥 尝试加载模型: {model_path}")
            try:
                # 方法1: 尝试直接加载
                checkpoint = torch.load(model_path, map_location=self.device, weights_only=False)

                # 检查checkpoint结构
                print(f"🔍 Checkpoint keys: {list(checkpoint.keys())}")

                # 尝试不同的键名
                if 'model_state_dict' in checkpoint:
                    state_dict = checkpoint['model_state_dict']
                elif 'state_dict' in checkpoint:
                    state_dict = checkpoint['state_dict']
                elif 'model' in checkpoint:
                    state_dict = checkpoint['model']
                else:
                    state_dict = checkpoint  # 直接是state_dict

                # 修复键名不匹配的问题
                new_state_dict = {}
                for k, v in state_dict.items():
                    # 移除可能的模块前缀
                    if k.startswith('module.'):
                        new_k = k[7:]  # 移除 'module.'
                    elif k.startswith('model.'):
                        new_k = k[6:]  # 移除 'model.'
                    else:
                        new_k = k
                    new_state_dict[new_k] = v

                # 加载修复后的state_dict
                model.load_state_dict(new_state_dict, strict=False)
                print("✅ 模型权重加载成功（使用strict=False）")

            except Exception as e:
                print(f"❌ 模型权重加载失败: {e}")
                print("🔄 尝试strict=False加载...")
                try:
                    model.load_state_dict(new_state_dict, strict=False)
                    print("✅ 模型权重加载成功（使用strict=False）")
                except Exception as e2:
                    print(f"❌ strict=False也失败: {e2}")
                    print("⚠️  使用随机初始化权重")
        else:
            print("⚠️  未找到预训练权重，使用随机初始化模型")

        # 统计模型参数
        total_params = sum(p.numel() for p in model.parameters())
        print(f"📈 模型参数总数: {total_params:,}")

        model = model.to(self.device)
        model.eval()
        return model

    def load_class_names(self):
        """加载植物类别名称映射"""
        class_file = "../shared/plant_classes.json"
        if os.path.exists(class_file):
            try:
                with open(class_file, 'r', encoding='utf-8') as f:
                    class_data = json.load(f)
                    print(f"✅ 加载植物类别: {len(class_data)} 种")
                    return class_data
            except Exception as e:
                print(f"❌ 类别文件加载失败: {e}")

        # 默认类别映射
        print("⚠️  使用默认植物类别映射")
        return {
            "0": {"name": "龟背竹", "sci_name": "Monstera deliciosa", "family": "天南星科"},
            "1": {"name": "栀子花", "sci_name": "Gardenia jasminoides", "family": "茜草科"},
            "2": {"name": "多肉植物", "sci_name": "Succulent plants", "family": "多个科属"},
            "3": {"name": "玫瑰", "sci_name": "Rosa rugosa", "family": "蔷薇科"},
            "4": {"name": "向日葵", "sci_name": "Helianthus annuus", "family": "菊科"}
        }

    def get_transform(self):
        """图像预处理转换"""
        return transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            )
        ])

    async def predict(self, image_path, top_k=3):
        """预测植物类别"""
        try:
            # 加载和预处理图像
            image = Image.open(image_path).convert('RGB')
            input_tensor = self.transform(image).unsqueeze(0).to(self.device)

            # 预测
            with torch.no_grad():
                outputs = self.model(input_tensor)
                probabilities = torch.nn.functional.softmax(outputs[0], dim=0)
                top_probs, top_indices = torch.topk(probabilities, top_k)

            # 构建结果
            results = []
            for i in range(top_k):
                class_idx = top_indices[i].item()
                confidence = top_probs[i].item()

                class_key = str(class_idx)
                if class_key in self.class_names:
                    plant_info = self.class_names[class_key].copy()
                    plant_info["confidence"] = confidence
                    plant_info["class_id"] = class_idx
                    results.append(plant_info)

            return {
                "success": True,
                "predictions": results,
                "top_prediction": results[0] if results else None
            }

        except Exception as e:
            print(f"❌ 预测失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "predictions": []
            }