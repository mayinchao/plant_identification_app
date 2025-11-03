import flet as ft
import sys
import datetime
import uuid
import aiohttp
import asyncio
import os
from flet import (
    AppBar, IconButton, Page, PopupMenuButton, PopupMenuItem, Text,
    ElevatedButton, Row, Column, Container, ScrollMode, Card, ListView, Divider,
    Image, SnackBar, TextField, Switch, FilePicker, FilePickerResultEvent,
    Stack, border_radius, AlertDialog, Icon, alignment, Colors
)


class PlantAPIClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url

    async def identify_plant(self, image_path):
        """调用植物识别API"""
        print("🌐 API客户端开始执行")
        print(f"🔗 目标URL: {self.base_url}/api/identify")
        print(f"📁 图片路径: {image_path}")

        try:
            # 检查文件
            if not os.path.exists(image_path):
                print("❌ 图片文件不存在")
                return {"success": False, "message": "图片文件不存在"}

            print("✅ 图片文件存在，准备发送请求")

            async with aiohttp.ClientSession() as session:
                with open(image_path, 'rb') as f:
                    form_data = aiohttp.FormData()
                    form_data.add_field('file', f, filename=os.path.basename(image_path))
                    print("✅ 表单数据准备完成")

                    try:
                        print("🚀 发送POST请求...")
                        async with session.post(
                                f"{self.base_url}/api/identify",
                                data=form_data,
                                timeout=aiohttp.ClientTimeout(total=30)
                        ) as response:
                            print(f"📥 收到响应，状态码: {response.status}")

                            if response.status == 200:
                                result = await response.json()
                                print(f"✅ API成功返回: {result}")
                                return result
                            else:
                                error_text = await response.text()
                                print(f"❌ API错误: {response.status} - {error_text}")
                                return {
                                    "success": False,
                                    "message": f"API请求失败: {response.status}"
                                }
                    except Exception as e:
                        print(f"🌐 网络请求异常: {e}")
                        return {
                            "success": False,
                            "message": f"网络请求异常: {str(e)}"
                        }

        except Exception as e:
            print(f"💥 API客户端异常: {e}")
            return {
                "success": False,
                "message": f"客户端异常: {str(e)}"
            }


class PlantIdentifierApp:
    def __init__(self, page: Page):
        # 页面基础配置
        self.page = page
        self.page.title = "青芜识界"
        self.page.theme_mode = ft.ThemeMode.LIGHT

        # API客户端
        self.api_client = PlantAPIClient()

        # 移动端检测和适配
        self.is_mobile = page.platform in ["android", "ios"]
        if self.is_mobile:
            self.page.bgcolor = Colors.LIGHT_GREEN_50
            self.plant_card_width = 300
            self.page.window_min_width = 0
            self.page.window_min_height = 0
        else:
            self.page.bgcolor = Colors.LIGHT_GREEN_50
            self.page.window_min_width = 600
            self.page.window_min_height = 400
            self.plant_card_width = max(150, self.page.width // 5)

        self.page.scroll = ScrollMode.AUTO

        # 图片选择相关
        self.image_picker = FilePicker(on_result=self.on_image_selected)
        self.page.overlay.append(self.image_picker)
        self.photo_preview = ft.Image(
            visible=False,
            width=400,
            height=300,
            fit=ft.ImageFit.COVER,
            border_radius=border_radius.all(8)
        )

        # 识别结果展示组件
        self.identification_result = Column(visible=False)

        # 用户资料
        self.user_info = {
            "username": "青芜用户",
            "user_id": "user_" + str(uuid.uuid4())[:8],
            "join_date": "2025-09-11",
            "bio": "热爱植物，喜欢探索自然的奥秘",
            "browsed": 52,
            "searched": 18,
            "avatar_url": "https://picsum.photos/200/200"
        }

        # 浏览历史和收藏记录
        self.browsing_history = []
        self.collected_plants = set()
        self.collection_history = []

        # 评论数据
        self.plant_comments = {}
        self.comment_visibility = {}
        self.user_reactions = {}

        # 通知相关
        self.notifications = []
        self.unread_count = 0
        self.badge_text = Text(
            str(self.unread_count) if self.unread_count <= 99 else "99+",
            size=10,
            color=Colors.WHITE,
            weight=ft.FontWeight.BOLD
        )
        self.notification_icon = IconButton(
            icon=ft.Icons.NOTIFICATIONS,
            on_click=lambda _: self.navigate_to_notification_page(),
            icon_size=24
        )
        self.notification_badge = Stack(
            controls=[
                self.notification_icon,
                Container(
                    content=self.badge_text,
                    bgcolor=Colors.RED,
                    width=18,
                    height=18,
                    alignment=alignment.center,
                    border_radius=border_radius.all(9),
                    visible=self.unread_count > 0
                )
            ],
            alignment=alignment.top_right
        )

        # 核心状态
        self.current_page_index = 0
        self.page_history = []
        self.current_tab_index = 0
        self.search_query = ""
        self.editing = False
        self.replying_to = None
        self.search_results = []

        # 所有植物数据
        self.all_plants = [
            {
                "name": "龟背竹",
                "desc": "多年生草本，喜温暖湿润",
                "image_url": "https://www.1818hm.com/file/upload/201608/31/1522546416.jpg",
                "sci_name": "Monstera deliciosa",
                "family": "天南星科 龟背竹属",
                "distribution": "原产墨西哥，现全球热带地区广泛栽培",
                "features": "茎干粗壮，节间短；叶片大，轮廓心状卵形，羽状分裂，革质，表面发亮；佛焰苞厚革质，宽卵形，舟状，近直立。",
                "habit": "喜温暖湿润环境，忌强光暴晒和干燥，耐阴，喜富含腐殖质的疏松土壤。适宜生长温度为20-30℃，冬季温度不低于5℃。",
                "culture": "叶片形态独特，酷似龟背，象征「健康长寿」，是常见的室内观叶植物。",
                "flower_language": "健康长寿",
                "poem": "叶似龟纹茎似竹，常青耐得暑寒侵。"
            },
            {
                "name": "栀子花",
                "desc": "木本植物，花期6-8月",
                "image_url": "https://imgs.bzw315.com/upload/2017/1/18/201701180942215643.jpg?x-oss-process=image/resize,w_640/sharpen,100/watermark,image_V2F0ZXJtYXJrLnBuZw==,t_90,g_center,x_10,y_10",
                "sci_name": "Gardenia jasminoides",
                "family": "茜草科 栀子属",
                "distribution": "原产中国，现世界各地广泛栽培",
                "features": "常绿灌木，高0.3-3米；嫩枝常被短毛，枝圆柱形，灰色。叶对生，革质，稀为纸质，少为3枚轮生，叶形多样。",
                "habit": "喜温暖湿润气候，好阳光但又不能经受强烈阳光照射，适宜生长在疏松、肥沃、排水良好、轻粘性酸性土壤中。",
                "culture": "栀子花在中国被视为吉祥如意、祥符瑞气的象征，其花语是「永恒的爱与约定」。",
                "flower_language": "永恒的爱与约定",
                "poem": "栀子比众木，人间诚未多。于身色有用，与道气伤和。"
            },
            {
                "name": "多肉植物",
                "desc": "耐旱怕涝，形态多样",
                "image_url": "https://ts3.tc.mm.bing.net/th/id/OIP-C.80VYr9icQIEbNN1G_PJ64QHaJr?cb=thfc1ucfimg=1&rs=1&pid=ImgDetMain&o=7&rm=3",
                "sci_name": "Succulent plants",
                "family": "多个科属的总称",
                "distribution": "全球广泛分布，主要生长在干旱或半干旱地区",
                "features": "指植物的根、茎、叶三种营养器官中的一种或几种退化变得肥厚多汁，用来贮藏水分的植物。",
                "habit": "喜欢阳光充足、通风良好的环境，耐旱性强，不耐水涝。",
                "culture": "近年来成为室内盆栽的热门选择，象征着坚韧不拔、顽强生命力。",
                "flower_language": "坚韧不拔",
                "poem": "碧瓦参差翡翠凉，小盆多肉缀新妆。"
            }
        ]

        # 头像上传选择器
        self.avatar_picker = FilePicker(on_result=self.on_avatar_selected)
        self.page.overlay.append(self.avatar_picker)

        # 初始化页面
        self.home_page = self.create_home_page()
        self.search_page = self.create_search_page()
        self.plant_page = self.create_plant_page()
        self.collection_page = self.create_collection_page()
        self.help_page = self.create_help_page()
        self.profile_page = self.create_profile_page()
        self.settings_page = self.create_settings_page()
        self.notification_page = self.create_notification_page()

        # 页面容器
        self.page_container = Container(
            content=Column([
                self.home_page,
                Container(
                    content=self.identification_result,
                    padding=10,
                    visible=True
                )
            ]),
            expand=True
        )

        # 自定义底部导航栏
        self.bottom_nav = Container(
            content=Row(
                [
                    Column(
                        controls=[
                            IconButton(
                                icon=ft.Icons.HOME_OUTLINED,
                                selected_icon=ft.Icons.HOME,
                                selected=False,
                                on_click=lambda e: self.on_custom_nav_click(0),
                                icon_size=24,
                                tooltip="首页",
                                icon_color=Colors.BLACK,
                            ),
                            Text("首页", size=12, color=Colors.BLACK)
                        ],
                        alignment=alignment.center,
                        spacing=2
                    ),
                    Column(
                        controls=[
                            IconButton(
                                icon=ft.Icons.SEARCH_OUTLINED,
                                selected_icon=ft.Icons.SEARCH,
                                selected=False,
                                on_click=lambda e: self.on_custom_nav_click(1),
                                icon_size=24,
                                tooltip="搜索",
                                icon_color=Colors.BLACK,
                            ),
                            Text("搜索", size=12, color=Colors.BLACK)
                        ],
                        alignment=alignment.center,
                        spacing=2
                    ),
                    Column(
                        controls=[
                            IconButton(
                                icon=ft.Icons.LIBRARY_BOOKS_OUTLINED,
                                selected_icon=ft.Icons.LIBRARY_BOOKS,
                                selected=False,
                                on_click=lambda e: self.on_custom_nav_click(2),
                                icon_size=24,
                                tooltip="植物资料",
                                icon_color=Colors.BLACK,
                            ),
                            Text("植物资料", size=12, color=Colors.BLACK)
                        ],
                        alignment=alignment.center,
                        spacing=2
                    ),
                    Column(
                        controls=[
                            IconButton(
                                icon=ft.Icons.COLLECTIONS_OUTLINED,
                                selected_icon=ft.Icons.COLLECTIONS,
                                selected=False,
                                on_click=lambda e: self.on_custom_nav_click(3),
                                icon_size=24,
                                tooltip="我的收藏",
                                icon_color=Colors.BLACK,
                            ),
                            Text("我的收藏", size=12, color=Colors.BLACK)
                        ],
                        alignment=alignment.center,
                        spacing=2
                    ),
                    Column(
                        controls=[
                            IconButton(
                                icon=ft.Icons.HELP_OUTLINED,
                                selected_icon=ft.Icons.HELP,
                                selected=False,
                                on_click=lambda e: self.on_custom_nav_click(4),
                                icon_size=24,
                                tooltip="帮助",
                                icon_color=Colors.BLACK,
                            ),
                            Text("帮助", size=12, color=Colors.BLACK)
                        ],
                        alignment=alignment.center,
                        spacing=2
                    ),
                ],
                alignment=alignment.center,
                vertical_alignment="end",
                spacing=20,
            ),
            bgcolor=Colors.WHITE,
            padding=10,
        )

        # 初始化组件与布局
        self.create_components()
        self.create_welcome_notification()
        self.assemble_page()
        self.update_navigation_state(0)

    def update_navigation_state(self, selected_index):
        """更新导航栏选中状态"""
        nav_row = self.bottom_nav.content
        for i, col in enumerate(nav_row.controls):
            icon_btn = col.controls[0]
            text = col.controls[1]
            if i == selected_index:
                icon_btn.selected = True
                icon_btn.icon_color = Colors.GREEN_600
                text.color = Colors.GREEN_600
            else:
                icon_btn.selected = False
                icon_btn.icon_color = Colors.BLACK
                text.color = Colors.BLACK

    def open_image_picker(self, e):
        """打开文件选择器选图"""
        self.image_picker.pick_files(
            allow_multiple=False,
            file_type=ft.FilePickerFileType.IMAGE,
            dialog_title="选择植物图片"
        )

    def on_image_selected(self, e: FilePickerResultEvent):
        """处理选图结果"""
        print("=" * 50)
        print("🔄 on_image_selected 方法被调用")

        if e.files:
            image_path = e.files[0].path
            print(f"🖼️ 选择的图片路径: {image_path}")

            # 显示图片预览
            self.photo_preview.src = image_path
            self.photo_preview.visible = True

            # 创建状态文本
            status_text = Text("准备开始识别...", size=14)
            preview_container = Container(
                content=Column([
                    self.photo_preview,
                    Container(height=10),
                    status_text
                ]),
                alignment=alignment.center,
                margin=ft.margin.symmetric(vertical=10)
            )

            # ========== 修复：替换而不是插入 ==========
            # 先移除可能存在的旧预览容器
            self.remove_existing_preview()

            # 添加到首页第3个位置（在图片识别区域下面）
            if len(self.home_page.controls) > 3:
                self.home_page.controls.insert(3, preview_container)
            else:
                self.home_page.controls.append(preview_container)
            # ========== 修复结束 ==========

            self.page.update()
            print("✅ 预览容器添加到页面")

            print("🚀 准备启动识别任务...")

            # 使用Flet的page.run_task来执行异步任务
            self.page.run_task(
                self.identify_plant_from_image,
                image_path,
                status_text
            )
            print("✅ 识别任务已通过page.run_task启动")
        else:
            print("❌ 没有选择文件")

        print("=" * 50)

    def remove_existing_preview(self):
        """移除已存在的图片预览容器"""
        print("🧹 清理旧预览容器...")

        # 查找并移除所有图片预览容器
        controls_to_remove = []
        for i, control in enumerate(self.home_page.controls):
            # 检查是否是预览容器（包含photo_preview）
            if (isinstance(control, Container) and
                    isinstance(control.content, Column) and
                    len(control.content.controls) > 0 and
                    control.content.controls[0] == self.photo_preview):
                controls_to_remove.append(i)
                print(f"🗑️ 找到旧预览容器，索引: {i}")

        # 从后往前移除，避免索引变化问题
        for index in sorted(controls_to_remove, reverse=True):
            if index < len(self.home_page.controls):
                self.home_page.controls.pop(index)
                print(f"✅ 移除索引 {index} 的预览容器")

        # 同时清空识别结果
        self.identification_result.controls.clear()
        self.identification_result.visible = False
        print("✅ 识别结果区域已清空")

    async def identify_plant_from_image(self, image_path, status_text):
        """识别植物并显示结果"""
        print("🎯 identify_plant_from_image 异步方法开始执行")
        print(f"📁 图片路径: {image_path}")
        print(f"🔤 状态文本对象: {status_text}")

        try:
            status_text.value = "🔄 正在识别植物..."
            status_text.color = Colors.BLUE
            print("✅ 状态文本已更新")
            self.page.update()
            print("✅ 页面已更新")

            # 调用API
            print("📞 开始调用API...")
            result = await self.api_client.identify_plant(image_path)
            print(f"📥 API返回结果: {result}")

            if result.get("success"):
                identification = result["identification"]
                top_plant = identification["top_prediction"]

                status_text.value = f"✅ 识别结果: {top_plant['name']} (置信度: {top_plant['confidence']:.2%})"
                status_text.color = Colors.GREEN
                print("✅ 识别成功，状态文本已更新")

                # 显示详细结果
                print("🎨 准备显示详细结果...")
                await self.show_identification_result(identification)

            else:
                status_text.value = f"❌ {result.get('message', '识别失败')}"
                status_text.color = Colors.RED
                print(f"❌ 识别失败: {result.get('message')}")

            self.page.update()
            print("✅ 最终页面更新完成")

        except Exception as e:
            print(f"💥 识别过程中发生异常: {e}")
            status_text.value = f"❌ 识别过程出错: {str(e)}"
            status_text.color = Colors.RED
            self.page.update()

        print("🏁 identify_plant_from_image 方法执行完成")

    async def show_identification_result(self, identification):
        """显示识别结果"""
        print("🎨 show_identification_result 开始")
        print(f"📊 识别数据: {identification}")

        top_plant = identification["top_prediction"]

        # 创建简单明确的结果显示
        result_content = Column([
            Text("🎉 识别完成！", size=20, weight=ft.FontWeight.BOLD, color=Colors.GREEN),
            Container(height=10),
            Text(f"植物名称: {top_plant['name']}", size=18, weight=ft.FontWeight.BOLD),
            Text(f"学名: {top_plant.get('sci_name', '未知')}", size=16),
            Text(f"置信度: {top_plant['confidence']:.2%}", size=16, color=Colors.BLUE),
        ])

        result_card = Card(
            content=Container(
                content=result_content,
                padding=20
            ),
            margin=10
        )

        print("🔄 更新识别结果区域...")

        # 确保识别结果区域存在且可见
        if not hasattr(self, 'identification_result'):
            print("❌ identification_result 不存在，创建新的")
            self.identification_result = Column(visible=True)

        self.identification_result.controls.clear()
        self.identification_result.controls.append(result_card)
        self.identification_result.visible = True

        print("✅ 结果区域更新完成，准备更新页面")

        # 强制更新页面
        self.page.update()
        print("✅ 页面更新完成")

    def create_components(self):
        """创建所有页面组件"""
        search_width = 300 if self.is_mobile else 400

        self.search_text = TextField(
            label="搜索植物名称或特征...",
            on_submit=self.handle_search,
            suffix_icon=IconButton(
                icon=ft.Icons.SEARCH,
                on_click=self.handle_search_click,
                tooltip="搜索"
            ),
            width=search_width,
            text_size=14
        )

        self.app_bar = AppBar(
            title=Text("青芜识界"),
            center_title=True,
            leading=IconButton(
                icon=ft.Icons.ARROW_BACK,
                on_click=self.go_back,
                disabled=True
            ),
            actions=[
                self.search_text,
                Container(
                    content=IconButton(
                        icon=ft.Icons.CAMERA_ALT,
                        on_click=self.open_image_picker,
                        tooltip="拍照识别植物",
                        icon_size=24,
                    ),
                    margin=ft.margin.symmetric(horizontal=5)
                ),
                Container(
                    content=IconButton(
                        icon=ft.Icons.UPLOAD_FILE,
                        on_click=self.open_image_picker,
                        tooltip="上传图片识别植物",
                        icon_size=24,
                    ),
                    margin=ft.margin.symmetric(horizontal=5)
                ),
                self.notification_badge,
                PopupMenuButton(
                    items=[
                        PopupMenuItem(
                            text="个人资料",
                            on_click=lambda _: self.navigate_to_page(self.profile_page, "个人资料")
                        ),
                        PopupMenuItem(
                            text="我的收藏",
                            on_click=lambda _: self.navigate_to_collection_page()
                        ),
                        PopupMenuItem(
                            text="设置",
                            on_click=lambda _: self.navigate_to_page(self.settings_page, "设置")
                        ),
                        PopupMenuItem(
                            text="退出",
                            on_click=lambda _: sys.exit()
                        ),
                    ]
                ),
            ],
        )

    def handle_search_click(self, e):
        self.navigate_to_search_page()
        self.handle_search(e)

    def _switch_page_content(self):
        if self.current_page_index == 0:
            self.page_container.content = Column([self.home_page, self.identification_result])
        elif self.current_page_index == 1:
            self.page_container.content = self.search_page
        elif self.current_page_index == 2:
            self.page_container.content = self.plant_page
        elif self.current_page_index == 3:
            self.page_container.content = self.collection_page
        elif self.current_page_index == 4:
            self.page_container.content = self.help_page
        self.page.update()

    def on_custom_nav_click(self, index):
        if index != self.current_page_index:
            self.page_history.append(self.current_page_index)
        self.current_page_index = index
        self._switch_page_content()
        self.app_bar.leading.disabled = len(self.page_history) == 0

        if index == 1:
            self.search_text.focus()

        self.update_navigation_state(index)
        self.page.update()

    def go_back(self, e):
        if len(self.page_history) > 0:
            last_index = self.page_history.pop()
            self.current_page_index = last_index
            self.update_navigation_state(last_index)
            self._switch_page_content()
            self.app_bar.leading.disabled = len(self.page_history) == 0
            snack = SnackBar(Text("返回上一页"))
            self.page.snack_bar = snack
            snack.open = True
            self.page.update()

    def navigate_to_home_page(self):
        if self.current_page_index != 0:
            self.page_history.append(self.current_page_index)
            self.current_page_index = 0
            self.update_navigation_state(0)
            self._switch_page_content()
            self.app_bar.leading.disabled = len(self.page_history) == 0
            self.page.update()

    def navigate_to_search_page(self):
        if self.current_page_index != 1:
            self.page_history.append(self.current_page_index)
            self.current_page_index = 1
            self.update_navigation_state(1)
            self._switch_page_content()
            self.search_text.focus()
            self.app_bar.leading.disabled = len(self.page_history) == 0
            self.page.update()

    def navigate_to_page(self, target_page, page_name):
        if self.page_container.content != target_page:
            self.page_history.append(self.current_page_index)
        self.page_container.content = target_page
        self.app_bar.title = Text(page_name)
        self.app_bar.leading.disabled = len(self.page_history) == 0
        self.page.update()

    def navigate_to_collection_page(self):
        if self.current_page_index != 3:
            self.page_history.append(self.current_page_index)
        self.current_page_index = 3
        self.update_navigation_state(3)
        self._switch_page_content()
        self.app_bar.leading.disabled = len(self.page_history) == 0
        self.page.update()

    def handle_search(self, e):
        query = self.search_text.value.strip().lower()
        self.search_query = query

        if self.current_page_index == 1:
            self.search_page.controls.clear()
            self.search_page.controls.extend([
                Container(height=20),
                Text("搜索植物名称或特征", size=18, weight=ft.FontWeight.BOLD),
                Container(height=10),
            ])

            if query:
                results = [
                    plant for plant in self.all_plants
                    if query in plant["name"].lower() or
                       query in plant["desc"].lower() or
                       query in plant["family"].lower() or
                       query in plant["features"].lower()
                ]
                self.search_results = results
                self.search_page.controls.append(Text(f"搜索结果: '{query}'", size=20, weight=ft.FontWeight.BOLD))
                self.search_page.controls.append(Container(height=10))

                if results:
                    result_cards = [self.create_plant_card_from_data(plant) for plant in results]
                    result_list = ListView(
                        controls=result_cards,
                        horizontal=False,
                        spacing=15,
                        expand=True
                    )
                    self.search_page.controls.append(result_list)
                else:
                    no_result = Container(
                        content=Column(
                            controls=[
                                IconButton(
                                    icon=ft.Icons.SEARCH_OFF,
                                    icon_size=48,
                                    disabled=True,
                                    icon_color=Colors.GREY_400
                                ),
                                Text(f"没有找到与 '{query}' 相关的植物", size=16, color=Colors.GREY_600)
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=10
                        ),
                        alignment=ft.alignment.center,
                        padding=ft.padding.all(20),
                        expand=True
                    )
                    self.search_page.controls.append(no_result)
            else:
                self.search_page.controls.append(
                    Container(
                        content=Column(
                            controls=[
                                IconButton(
                                    icon=ft.Icons.SEARCH,
                                    icon_size=48,
                                    disabled=True,
                                    icon_color=Colors.GREY_400
                                ),
                                Text("请输入植物名称或特征进行搜索", size=16, color=Colors.GREY_600)
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=10
                        ),
                        alignment=ft.alignment.center,
                        padding=ft.padding.all(20),
                        expand=True
                    )
                )

            self.page.update()

    def reset_home_page_content(self):
        self.home_page.controls.clear()
        featured_plants = [self.create_plant_card_from_data(plant) for plant in self.all_plants]
        self.home_page.controls = [
            Container(height=20),
            Text("欢迎使用青芜识界", size=24, weight=ft.FontWeight.BOLD),
            Divider(height=20),
            Text("青芜在侧，识得草木名", size=16, color=Colors.GREY_700),
            Container(height=20),
            Text("精选植物", size=20, weight=ft.FontWeight.BOLD),
            Container(height=10),
            ListView(
                controls=featured_plants,
                horizontal=False,
                spacing=15,
                expand=True
            ),
            Container(height=20),
            Card(
                content=Column(
                    controls=[
                        Container(height=10),
                        Text("植物小知识", size=18, weight=ft.FontWeight.BOLD),
                        ListView(
                            controls=[
                                Text("1. 植物的光合作用需要叶绿素、光和二氧化碳。"),
                                Text("2. 多肉植物的叶片肥厚，是为了储存水分应对干旱。"),
                                Text("3. 有些植物（如含羞草）受触碰后叶片闭合，是应激反应。")
                            ],
                            expand=True,
                            spacing=5
                        ),
                        Container(height=10)
                    ],
                    spacing=10
                )
            ),
            Container(height=20)
        ]

    def create_home_page(self):
        featured_plants = [self.create_plant_card_from_data(plant) for plant in self.all_plants]

        # 图片识别区域
        image_recognition_section = Card(
            content=Container(
                content=Column([
                    Text("植物图片识别", size=20, weight=ft.FontWeight.BOLD),
                    Container(height=10),
                    Text("上传植物图片，AI智能识别植物种类", size=14, color=Colors.GREY_600),
                    Container(height=15),
                    ElevatedButton(
                        "📸 上传图片识别植物",
                        icon=ft.Icons.UPLOAD_FILE,
                        on_click=self.open_image_picker,
                        style=ft.ButtonStyle(
                            bgcolor=Colors.GREEN_600,
                            color=Colors.WHITE,
                            padding=20
                        ),
                        width=250
                    ),
                    Container(height=10),
                    Text("支持 JPG、PNG 格式图片", size=12, color=Colors.GREY_500)
                ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=20,
                alignment=ft.alignment.center
            ),
            margin=ft.margin.symmetric(vertical=10)
        )

        return Column(
            controls=[
                Container(height=20),
                Text("欢迎使用青芜识界", size=24, weight=ft.FontWeight.BOLD),
                Divider(height=20),
                Text("青芜在侧，识得草木名", size=16, color=Colors.GREY_700),
                Container(height=20),

                # 添加图片识别区域
                image_recognition_section,
                Container(height=20),

                # 识别结果区域 - 确保有空间显示
                Container(
                    content=self.identification_result,
                    padding=10
                ),

                Text("精选植物", size=20, weight=ft.FontWeight.BOLD),
                Container(height=10),
                ListView(
                    controls=featured_plants,
                    horizontal=False,
                    spacing=15,
                    expand=True
                ),
                Container(height=20),
                Card(
                    content=Column(
                        controls=[
                            Container(height=10),
                            Text("植物小知识", size=18, weight=ft.FontWeight.BOLD),
                            ListView(
                                controls=[
                                    Text("1. 植物的光合作用需要叶绿素、光和二氧化碳。"),
                                    Text("2. 多肉植物的叶片肥厚，是为了储存水分应对干旱。"),
                                    Text("3. 有些植物（如含羞草）受触碰后叶片闭合，是应激反应。")
                                ],
                                expand=True,
                                spacing=5
                            ),
                            Container(height=10)
                        ],
                        spacing=10
                    )
                ),
                Container(height=20)
            ],
            expand=True,
            spacing=0,
            scroll=ScrollMode.AUTO  # 确保可以滚动
        )

    def create_search_page(self):
        return Column(
            controls=[
                Container(height=20),
                Text("搜索植物名称或特征", size=18, weight=ft.FontWeight.BOLD),
                Container(height=10),
            ],
            expand=True,
            spacing=0
        )

    def create_plant_card_from_data(self, plant_data):
        card_content = Row(
            controls=[
                Column(
                    controls=[
                        Image(
                            src=plant_data["image_url"],
                            width=self.plant_card_width,
                            height=int(self.plant_card_width * 0.75),
                            fit=ft.ImageFit.COVER
                        ),
                        Container(height=10),
                        Text(plant_data["name"], weight=ft.FontWeight.BOLD, size=14),
                        Text(plant_data["desc"], size=12, color=Colors.GREY_600, max_lines=2),
                    ],
                    spacing=0,
                    alignment=ft.MainAxisAlignment.START,
                    width=self.plant_card_width,
                ),
                Container(
                    content=Column(
                        controls=[
                            Container(height=20),
                            Text(f"花语：{plant_data.get('flower_language', '暂无')}", size=12, color=Colors.GREY_700),
                            Container(height=5),
                            Text(f"诗句：{plant_data.get('poem', '暂无')}", size=12, color=Colors.GREY_700, max_lines=3),
                        ],
                        spacing=3,
                        alignment=ft.MainAxisAlignment.START,
                        expand=True
                    ),
                    padding=10
                ),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )
        clickable_container = Container(
            content=card_content,
            expand=True,
            on_click=lambda e, data=plant_data: self.navigate_to_plant_detail(data)
        )
        return Card(
            content=clickable_container,
            elevation=3,
            margin=ft.margin.all(10),
        )

    def create_history_card(self, item, is_collection=False, show_delete=False):
        """创建历史/收藏卡片"""
        plant_data = item["plant"]
        time_str = item["time"].strftime("%Y-%m-%d %H:%M")
        right_controls = []
        if is_collection:
            right_controls.append(Container(
                content=IconButton(
                    icon=ft.Icons.STAR,
                    bgcolor=Colors.YELLOW_500,
                    tooltip="已收藏"
                ),
                margin=ft.margin.symmetric(horizontal=2)
            ))
        else:
            right_controls.append(Container(
                content=IconButton(
                    icon=ft.Icons.HISTORY,
                    bgcolor=Colors.GREY_500,
                    tooltip="浏览记录"
                ),
                margin=ft.margin.symmetric(horizontal=2)
            ))
        if show_delete:
            if is_collection:
                right_controls.append(Container(
                    content=IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        bgcolor=Colors.RED_500,
                        tooltip="删除收藏",
                        on_click=lambda e, plant_name=plant_data["name"]: self.remove_from_collection(e, plant_name)
                    ),
                    margin=ft.margin.symmetric(horizontal=2)
                ))
            else:
                right_controls.append(Container(
                    content=IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        bgcolor=Colors.RED_500,
                        tooltip="删除浏览记录",
                        on_click=lambda e, item=item: self.delete_browsing_history(item)
                    ),
                    margin=ft.margin.symmetric(horizontal=2)
                ))
        card_content = Row(
            controls=[
                Image(
                    src=plant_data["image_url"],
                    width=80,
                    height=80,
                    fit=ft.ImageFit.COVER
                ),
                Column(
                    controls=[
                        Text(plant_data["name"], weight=ft.FontWeight.BOLD),
                        Text(f"科属：{plant_data['family']}", size=12),
                        Text(time_str, size=11, color=Colors.GREY_500)
                    ],
                    spacing=3,
                    expand=True
                ),
                Row(controls=right_controls, spacing=0)
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        )
        clickable_container = Container(
            content=card_content,
            expand=True,
            on_click=lambda e, data=plant_data: self.navigate_to_plant_detail(data)
        )
        return Card(
            content=clickable_container,
            elevation=2,
            margin=ft.margin.symmetric(vertical=5)
        )

    def delete_browsing_history(self, item):
        """删除浏览记录"""
        plant_name = item["plant"]["name"]
        plant_time = item["time"]
        for i, history_item in enumerate(self.browsing_history):
            if history_item["plant"]["name"] == plant_name and history_item["time"] == plant_time:
                del self.browsing_history[i]
                break
        self.update_profile_history_lists()
        snack = SnackBar(Text(f"已删除{plant_name}的浏览记录"))
        self.page.snack_bar = snack
        snack.open = True
        self.page.update()

    def create_comment_component(self, comment, plant_name, depth=0):
        """创建评论组件（支持嵌套/互动）"""
        comment_id = comment["id"]
        is_owner = comment["user_id"] == self.user_info["user_id"]
        is_expanded = self.comment_visibility.get(comment_id, True)
        user_reaction = self.user_reactions.get(comment_id)
        replies = [c for c in self.plant_comments.get(plant_name, []) if c["parent_id"] == comment_id]
        like_color = Colors.BLUE if user_reaction == "like" else Colors.GREY
        dislike_color = Colors.RED if user_reaction == "dislike" else Colors.GREY
        comment_content = Column(
            controls=[
                Row(
                    controls=[
                        Text(comment["user"], weight=ft.FontWeight.BOLD, size=14),
                        Text(comment["time"].strftime("%Y-%m-%d %H:%M"), size=12, color=Colors.GREY_500),
                        IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            icon_size=16,
                            tooltip="删除评论",
                            on_click=lambda e, cid=comment_id, pname=plant_name: self.delete_comment(e, cid, pname),
                            visible=is_owner
                        ) if is_owner else Container()
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                ),
                Container(height=5),
                Text(comment["content"], size=14),
                Container(height=5),
                Row(
                    controls=[
                        Container(
                            content=Column(
                                controls=[
                                    IconButton(
                                        icon=ft.Icons.THUMB_UP,
                                        icon_size=16,
                                        tooltip="喜欢",
                                        on_click=lambda e, cid=comment_id, rt="like", pname=plant_name:
                                        self.handle_reaction(e, cid, rt, pname),
                                        icon_color=like_color,
                                        padding=2
                                    ),
                                    Text(str(comment["likes"]), size=11)
                                ],
                                alignment=ft.MainAxisAlignment.CENTER,
                                spacing=1
                            ),
                            width=40
                        ),
                        Container(
                            content=Column(
                                controls=[
                                    IconButton(
                                        icon=ft.Icons.THUMB_DOWN,
                                        icon_size=16,
                                        tooltip="不喜欢",
                                        on_click=lambda e, cid=comment_id, rt="dislike", pname=plant_name:
                                        self.handle_reaction(e, cid, rt, pname),
                                        icon_color=dislike_color,
                                        padding=2
                                    ),
                                    Text(str(comment["dislikes"]), size=11)
                                ],
                                alignment=ft.MainAxisAlignment.CENTER,
                                spacing=1
                            ),
                            width=40
                        ),
                        Container(
                            content=IconButton(
                                icon=ft.Icons.REPLY,
                                icon_size=16,
                                tooltip="回复",
                                on_click=lambda e, cid=comment_id: self.start_reply(cid),
                                padding=2
                            ),
                            width=30
                        ),
                    ],
                    spacing=5,
                    alignment=ft.MainAxisAlignment.START
                ),
                Container(height=5),
                ft.Container(
                    content=Row(
                        controls=[
                            TextField(
                                hint_text=f"回复 @{comment['user']}...",
                                multiline=True,
                                min_lines=1,
                                max_lines=3,
                                expand=True,
                                on_submit=lambda e, pid=comment_id, pname=plant_name:
                                self.add_reply(e, pid, pname)
                            ),
                            ElevatedButton(
                                text="回复",
                                on_click=lambda e, pid=comment_id, pname=plant_name:
                                self.add_reply(e, pid, pname),
                                style=ft.ButtonStyle(
                                    bgcolor=Colors.GREEN_600,
                                    color=Colors.WHITE,
                                    padding=5
                                ),
                                height=32
                            )
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.START
                    ),
                    visible=self.replying_to == comment_id,
                    margin=ft.margin.only(left=10)
                ) if self.replying_to == comment_id else Container(),
                IconButton(
                    icon=ft.Icons.EXPAND_MORE if is_expanded else ft.Icons.EXPAND_LESS,
                    icon_size=16,
                    tooltip="折叠/展开回复",
                    on_click=lambda e, cid=comment_id, pname=plant_name:
                    self.toggle_comment_thread(e, cid, pname),
                    visible=len(replies) > 0,
                    padding=2
                ) if len(replies) > 0 else Container(),
                ft.Container(
                    content=Column(
                        controls=[self.create_comment_component(reply, plant_name, depth + 1) for reply in replies],
                        spacing=8
                    ),
                    margin=ft.margin.only(left=20),
                    visible=is_expanded and len(replies) > 0
                )
            ],
            spacing=0
        )
        return Card(
            content=Container(
                content=comment_content,
                padding=10
            ),
            elevation=2,
            margin=ft.margin.symmetric(vertical=5)
        )

    def start_reply(self, comment_id):
        """开始回复某条评论"""
        self.replying_to = comment_id if self.replying_to != comment_id else None
        self.update_comments_list(self.plant_name.value)
        self.page.update()

    def add_reply(self, e, parent_id, plant_name):
        """添加回复评论"""
        reply_input = None
        for ctrl in e.control.parent.controls:
            if isinstance(ctrl, TextField):
                reply_input = ctrl
                break
        if not reply_input or not reply_input.value.strip():
            return
        comment_text = reply_input.value.strip()
        if plant_name not in self.plant_comments:
            self.plant_comments[plant_name] = []
        new_comment = {
            "id": str(uuid.uuid4())[:10],
            "user": self.user_info["username"],
            "user_id": self.user_info["user_id"],
            "content": comment_text,
            "time": datetime.datetime.now(),
            "parent_id": parent_id,
            "likes": 0,
            "dislikes": 0
        }
        self.plant_comments[plant_name].insert(0, new_comment)
        self.replying_to = None
        if reply_input:
            reply_input.value = ""
        self.update_comments_list(plant_name)
        snack = SnackBar(Text("回复已发布"))
        self.page.snack_bar = snack
        snack.open = True
        self.page.update()

    def toggle_comment_thread(self, e, comment_id, plant_name):
        """折叠/展开评论线程"""
        self.comment_visibility[comment_id] = not self.comment_visibility.get(comment_id, True)
        self.update_comments_list(plant_name)
        self.page.update()

    def handle_reaction(self, e, comment_id, reaction_type, plant_name):
        """处理点赞/点踩"""
        if plant_name not in self.plant_comments:
            return
        for comment in self.plant_comments[plant_name]:
            if comment["id"] == comment_id:
                current_reaction = self.user_reactions.get(comment_id)
                if current_reaction == reaction_type:
                    comment[reaction_type + "s"] -= 1
                    del self.user_reactions[comment_id]
                else:
                    if current_reaction:
                        comment[current_reaction + "s"] -= 1
                    comment[reaction_type + "s"] += 1
                    self.user_reactions[comment_id] = reaction_type
                break
        self.update_comments_list(plant_name)
        self.page.update()

    def delete_comment(self, e, comment_id, plant_name):
        """删除自己的评论（含子评论）"""
        if plant_name not in self.plant_comments:
            return

        def find_all_children(cid):
            children = [cid]
            for comment in self.plant_comments[plant_name]:
                if comment["parent_id"] == cid:
                    children.extend(find_all_children(comment["id"]))
            return children

        comments_to_delete = find_all_children(comment_id)
        self.plant_comments[plant_name] = [
            c for c in self.plant_comments[plant_name]
            if c["id"] not in comments_to_delete
        ]
        for cid in comments_to_delete:
            if cid in self.user_reactions:
                del self.user_reactions[cid]
            if cid in self.comment_visibility:
                del self.comment_visibility[cid]
        self.update_comments_list(plant_name)
        snack = SnackBar(Text("评论已删除"))
        self.page.snack_bar = snack
        snack.open = True
        self.page.update()

    def add_comment(self, e, plant_name):
        """添加顶级评论"""
        comment_text = self.comment_input.value.strip()
        if not comment_text:
            return
        if plant_name not in self.plant_comments:
            self.plant_comments[plant_name] = []
        new_comment = {
            "id": str(uuid.uuid4())[:10],
            "user": self.user_info["username"],
            "user_id": self.user_info["user_id"],
            "content": comment_text,
            "time": datetime.datetime.now(),
            "parent_id": None,
            "likes": 0,
            "dislikes": 0
        }
        self.plant_comments[plant_name].insert(0, new_comment)
        self.comment_input.value = ""
        self.update_comments_list(plant_name)
        snack = SnackBar(Text("评论已发布"))
        self.page.snack_bar = snack
        snack.open = True
        self.page.update()

    def update_comments_list(self, plant_name):
        """更新评论列表"""
        self.comments_list.controls.clear()
        if plant_name in self.plant_comments and self.plant_comments[plant_name]:
            top_level_comments = [c for c in self.plant_comments[plant_name] if c["parent_id"] is None]
            for comment in top_level_comments:
                self.comments_list.controls.append(self.create_comment_component(comment, plant_name))
        else:
            self.comments_list.controls.append(Text("暂无评论，快来发表第一条评论吧！", color=Colors.GREY_500))
        self.page.update()

    def create_plant_page(self):
        """创建植物详情页（含评论互动）"""
        default_plant = self.all_plants[0]
        self.plant_name = Text(default_plant["name"], size=24, weight=ft.FontWeight.BOLD)
        img_width, img_height = self.get_responsive_image_dimensions()
        self.plant_image = Image(
            src=default_plant["image_url"],
            width=img_width,
            height=img_height,
            fit=ft.ImageFit.CONTAIN
        )
        self.plant_sci_name = Text(f"学名：{default_plant['sci_name']}")
        self.plant_family = Text(f"科属：{default_plant['family']}")
        self.plant_distribution = Text(f"分布区域：{default_plant['distribution']}")
        self.plant_features = Text(f"形态特征：{default_plant['features']}")
        self.plant_habit_text = Text(default_plant['habit'])
        self.plant_culture_text = Text(default_plant['culture'])
        self.basic_info_content = Column(
            controls=[
                self.plant_sci_name,
                self.plant_family,
                self.plant_distribution,
                Container(height=10),
                Text("形态特征：", weight=ft.FontWeight.BOLD),
                self.plant_features,
            ],
            spacing=8,
            expand=True,
            visible=True
        )
        self.habit_content = Column(
            controls=[
                Text("生长习性：", weight=ft.FontWeight.BOLD),
                self.plant_habit_text,
            ],
            spacing=8,
            expand=True,
            visible=False
        )
        self.culture_content = Column(
            controls=[
                Text("植物文化：", weight=ft.FontWeight.BOLD),
                self.plant_culture_text,
            ],
            spacing=8,
            expand=True,
            visible=False
        )

        def switch_tab(index):
            self.basic_info_content.visible = False
            self.habit_content.visible = False
            self.culture_content.visible = False
            if index == 0:
                self.basic_info_content.visible = True
            elif index == 1:
                self.habit_content.visible = True
            elif index == 2:
                self.culture_content.visible = True
            self.current_tab_index = index
            basic_info_btn.style.bgcolor = Colors.GREEN_600 if index == 0 else Colors.WHITE
            basic_info_btn.style.color = Colors.WHITE if index == 0 else Colors.BLACK
            habit_btn.style.bgcolor = Colors.GREEN_600 if index == 1 else Colors.WHITE
            habit_btn.style.color = Colors.WHITE if index == 1 else Colors.BLACK
            culture_btn.style.bgcolor = Colors.GREEN_600 if index == 2 else Colors.WHITE
            culture_btn.style.color = Colors.WHITE if index == 2 else Colors.BLACK
            self.page.update()

        basic_info_btn = ElevatedButton(
            text="基本信息",
            on_click=lambda _: switch_tab(0),
            style=ft.ButtonStyle(
                bgcolor=Colors.GREEN_600 if self.current_tab_index == 0 else Colors.WHITE,
                color=Colors.WHITE if self.current_tab_index == 0 else Colors.BLACK
            )
        )
        habit_btn = ElevatedButton(
            text="生长习性",
            on_click=lambda _: switch_tab(1),
            style=ft.ButtonStyle(
                bgcolor=Colors.GREEN_600 if self.current_tab_index == 1 else Colors.WHITE,
                color=Colors.WHITE if self.current_tab_index == 1 else Colors.BLACK
            )
        )
        culture_btn = ElevatedButton(
            text="植物文化",
            on_click=lambda _: switch_tab(2),
            style=ft.ButtonStyle(
                bgcolor=Colors.GREEN_600 if self.current_tab_index == 2 else Colors.WHITE,
                color=Colors.WHITE if self.current_tab_index == 2 else Colors.BLACK
            )
        )
        tabs_buttons = Row(controls=[basic_info_btn, habit_btn, culture_btn], spacing=10)
        content_container = Column(
            controls=[
                Container(height=10),
                self.basic_info_content,
                self.habit_content,
                self.culture_content,
                Container(height=10)
            ],
            expand=True,
            spacing=0
        )
        self.favorite_button = ElevatedButton(
            text="收藏该植物",
            icon=ft.Icons.STAR if self.plant_name.value in self.collected_plants else ft.Icons.STAR_BORDER,
            on_click=self.toggle_collection,
            width=200,
            style=ft.ButtonStyle(
                bgcolor=Colors.GREEN_600,
                color=Colors.WHITE
            )
        )
        self.comment_input = TextField(
            hint_text="添加评论...",
            multiline=True,
            min_lines=2,
            max_lines=3,
            expand=True
        )
        self.comments_list = ListView(expand=True, spacing=5)
        self.update_comments_list(default_plant["name"])
        comment_section = Column(
            controls=[
                Text("用户评论", size=18, weight=ft.FontWeight.BOLD),
                Divider(height=10),
                Row(
                    controls=[
                        self.comment_input,
                        ElevatedButton(
                            text="发布",
                            on_click=lambda e: self.add_comment(e, self.plant_name.value),
                            style=ft.ButtonStyle(
                                bgcolor=Colors.GREEN_600,
                                color=Colors.WHITE
                            ),
                            height=50
                        )
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.START
                ),
                Container(height=10),
                self.comments_list
            ],
            expand=True,
            spacing=10
        )
        return Column(
            controls=[
                Container(height=20),
                self.plant_name,
                Divider(height=20),
                Container(
                    content=self.plant_image,
                    alignment=ft.alignment.center,
                    height=img_height
                ),
                Container(height=20),
                tabs_buttons,
                Divider(height=10),
                content_container,
                Container(height=20),
                Container(
                    content=self.favorite_button,
                    alignment=ft.alignment.center,
                ),
                Container(height=20),
                Divider(height=20),
                comment_section,
                Container(height=20)
            ],
            spacing=0,
            expand=True
        )

    def toggle_collection(self, e):
        """切换植物收藏状态"""
        plant_name = self.plant_name.value
        current_plant = next((p for p in self.all_plants if p["name"] == plant_name), None)
        if not current_plant:
            return
        if plant_name in self.collected_plants:
            self.collected_plants.remove(plant_name)
            self.favorite_button.icon = ft.Icons.STAR_BORDER
            snack = SnackBar(Text(f"已取消收藏{plant_name}"))
            for i, item in enumerate(self.collection_history):
                if item["plant"]["name"] == plant_name:
                    del self.collection_history[i]
                    break
        else:
            self.collected_plants.add(plant_name)
            self.favorite_button.icon = ft.Icons.STAR
            snack = SnackBar(Text(f"已收藏{plant_name}"))
            self.collection_history.insert(0, {"plant": current_plant, "time": datetime.datetime.now()})
            if len(self.collection_history) > 20:
                self.collection_history.pop()
        self.update_collection_list()
        self.update_profile_history_lists()
        self.page.snack_bar = snack
        snack.open = True
        self.page.update()

    def update_collection_list(self):
        """更新收藏页列表"""
        if not hasattr(self, 'collection_list'):
            return
        self.collection_list.controls.clear()
        if not self.collected_plants:
            self.collection_list.controls.append(Text("您还没有收藏任何植物，浏览植物后可收藏喜欢的植物"))
        else:
            for item in self.collection_history:
                self.collection_list.controls.append(
                    self.create_history_card(item, is_collection=True, show_delete=True))

    def update_profile_history_lists(self):
        """更新个人资料页的历史/收藏列表"""
        if not hasattr(self, 'browsing_history_list') or not hasattr(self, 'collection_history_list'):
            return
        self.browsing_history_list.controls.clear()
        if not self.browsing_history:
            self.browsing_history_list.controls.append(Text("暂无浏览记录"))
        else:
            for item in self.browsing_history[:10]:
                self.browsing_history_list.controls.append(
                    self.create_history_card(item, is_collection=False, show_delete=True))
        self.collection_history_list.controls.clear()
        if not self.collection_history:
            self.collection_history_list.controls.append(Text("暂无收藏记录"))
        else:
            for item in self.collection_history[:10]:
                self.collection_history_list.controls.append(
                    self.create_history_card(item, is_collection=True, show_delete=True))

    def remove_from_collection(self, e, plant_name):
        """从收藏中移除植物"""
        if plant_name in self.collected_plants:
            self.collected_plants.remove(plant_name)
            if hasattr(self, 'favorite_button') and self.plant_name.value == plant_name:
                self.favorite_button.icon = ft.Icons.STAR_BORDER
        for i, item in enumerate(self.collection_history):
            if item["plant"]["name"] == plant_name:
                del self.collection_history[i]
                break
        self.update_collection_list()
        self.update_profile_history_lists()
        snack = SnackBar(Text(f"已删除{plant_name}的收藏"))
        self.page.snack_bar = snack
        snack.open = True
        self.page.update()

    def navigate_to_plant_detail(self, plant_data):
        """跳转到植物详情页（记录浏览历史）"""
        self.add_to_browsing_history(plant_data)
        if self.current_page_index != 2:
            self.page_history.append(self.current_page_index)
        self.current_page_index = 2
        self.update_navigation_state(2)
        self._switch_page_content()
        self.app_bar.leading.disabled = len(self.page_history) == 0
        self.plant_name.value = plant_data["name"]
        self.plant_image.src = plant_data["image_url"]
        self.plant_sci_name.value = f"学名：{plant_data['sci_name']}"
        self.plant_family.value = f"科属：{plant_data['family']}"
        self.plant_distribution.value = f"分布区域：{plant_data['distribution']}"
        self.plant_features.value = plant_data["features"]
        self.plant_habit_text.value = plant_data["habit"]
        self.plant_culture_text.value = plant_data["culture"]
        self.basic_info_content.visible = True
        self.habit_content.visible = False
        self.culture_content.visible = False
        self.current_tab_index = 0
        self.favorite_button.icon = ft.Icons.STAR if plant_data[
                                                         "name"] in self.collected_plants else ft.Icons.STAR_BORDER
        self.update_comments_list(plant_data["name"])
        self.page.update()

    def add_to_browsing_history(self, plant_data):
        """添加到浏览历史"""
        for i, item in enumerate(self.browsing_history):
            if item["plant"]["name"] == plant_data["name"]:
                del self.browsing_history[i]
                break
        self.browsing_history.insert(0, {"plant": plant_data, "time": datetime.datetime.now()})
        if len(self.browsing_history) > 20:
            self.browsing_history.pop()
        self.update_profile_history_lists()

    def create_collection_page(self):
        """创建收藏页"""
        self.collection_list = ListView(
            controls=[Text("您还没有收藏任何植物，浏览植物后可收藏喜欢的植物")],
            expand=True,
            spacing=10
        )
        return Column(
            controls=[
                Container(height=20),
                Text("我的收藏", size=24, weight=ft.FontWeight.BOLD),
                Divider(height=20),
                self.collection_list,
                Container(height=20)
            ],
            expand=True,
            spacing=0
        )

    def create_help_page(self):
        """创建帮助页"""
        return Column(
            controls=[
                Container(height=20),
                Text("帮助中心", size=24, weight=ft.FontWeight.BOLD),
                Divider(height=20),
                Text("常见问题", size=18, weight=ft.FontWeight.BOLD),
                ListView(
                    controls=[
                        Text("Q: 如何浏览植物资料？\nA: 在首页点击植物卡片即可查看详情。"),
                        Text(
                            "Q: 如何搜索植物？\nA: 在顶部搜索框输入关键词，按回车或点击搜索图标，会跳转到搜索页面显示结果。"),
                        Text("Q: 如何收藏喜欢的植物？\nA: 在植物资料页点击「收藏该植物」按钮。"),
                        Text("Q: 如何发表评论？\nA: 在植物资料页底部评论区输入内容并点击发布按钮。"),
                        Text("Q: 如何回复他人评论？\nA: 点击评论下方的回复按钮，输入内容后提交。"),
                        Text("Q: 如何删除自己的评论？\nA: 在自己的评论右上角点击删除按钮。"),
                        Text("Q: 如何对评论进行点赞/点踩？\nA: 点击评论下方的大拇指图标。"),
                        Text("Q: 如何删除浏览/收藏记录？\nA: 在个人资料页或收藏页点击记录右侧的删除按钮。"),
                        Text("Q: 如何上传植物图片？\nA: 点击顶部搜索框旁的上传图标，选择本地植物图片即可。")
                    ],
                    expand=True,
                    spacing=10
                ),
                Container(height=20),
                Container(
                    content=ElevatedButton(
                        text="联系客服",
                        on_click=self.contact_support,
                        width=150,
                    ),
                    alignment=ft.alignment.center,
                ),
                Container(height=20)
            ],
            expand=True,
            spacing=0
        )

    def create_profile_page(self):
        """创建个人资料页"""
        self.username_field = TextField(
            value=self.user_info["username"],
            label="用户名",
            visible=False,
            width=300
        )
        self.bio_field = TextField(
            value=self.user_info["bio"],
            label="个人简介",
            multiline=True,
            min_lines=3,
            max_lines=5,
            visible=False,
            width=300
        )
        self.avatar_image = Image(
            src=self.user_info["avatar_url"],
            width=100,
            height=100,
            fit=ft.ImageFit.COVER,
            border_radius=ft.border_radius.all(50)
        )
        self.change_avatar_btn = ElevatedButton(
            text="更换头像",
            icon=ft.Icons.CAMERA_ALT,
            on_click=lambda _: self.avatar_picker.pick_files(
                allow_multiple=False,
                file_type=ft.FilePickerFileType.IMAGE
            ),
            visible=False,
            style=ft.ButtonStyle(
                bgcolor=Colors.GREY_200,
                color=Colors.BLACK
            )
        )
        self.username_text = Text(self.user_info["username"], size=18, weight=ft.FontWeight.BOLD)
        self.bio_text = Text(self.user_info["bio"], size=14, color=Colors.GREY_700)
        self.browsing_history_list = ListView(
            controls=[Text("暂无浏览记录")],
            expand=True,
            spacing=5
        )
        self.collection_history_list = ListView(
            controls=[Text("暂无收藏记录")],
            expand=True,
            spacing=5
        )

        def toggle_edit(e):
            self.editing = not self.editing
            self.username_text.visible = not self.editing
            self.username_field.visible = self.editing
            self.bio_text.visible = not self.editing
            self.bio_field.visible = self.editing
            self.change_avatar_btn.visible = self.editing
            if self.editing:
                edit_button.text = "保存"
                edit_button.on_click = save_profile
                self.username_field.value = self.user_info["username"]
                self.bio_field.value = self.user_info["bio"]
            else:
                edit_button.text = "编辑资料"
                edit_button.on_click = toggle_edit
            self.page.update()

        def save_profile(e):
            self.user_info["username"] = self.username_field.value
            self.user_info["bio"] = self.bio_field.value
            self.username_text.value = self.user_info["username"]
            self.bio_text.value = self.user_info["bio"]
            toggle_edit(None)
            snack = SnackBar(Text("个人资料已更新"))
            self.page.snack_bar = snack
            snack.open = True
            self.page.update()

        edit_button = ElevatedButton(
            text="编辑资料",
            on_click=toggle_edit,
            icon=ft.Icons.EDIT,
            style=ft.ButtonStyle(
                bgcolor=Colors.GREEN_600,
                color=Colors.WHITE
            )
        )
        return Column(
            controls=[
                Container(height=20),
                Text("个人资料", size=24, weight=ft.FontWeight.BOLD),
                Divider(height=20),
                Card(
                    content=Column(
                        controls=[
                            Container(height=20),
                            Row(
                                controls=[
                                    Container(
                                        content=Column(
                                            controls=[
                                                self.avatar_image,
                                                self.change_avatar_btn
                                            ],
                                            alignment=ft.MainAxisAlignment.CENTER,
                                            spacing=10
                                        ),
                                        border_radius=ft.border_radius.all(50),
                                        bgcolor=Colors.GREY_200,
                                        padding=2
                                    ),
                                    Column(
                                        controls=[
                                            self.username_text,
                                            self.username_field,
                                            Text(f"注册时间：{self.user_info['join_date']}", size=14,
                                                 color=Colors.GREY_600),
                                            Text(f"收藏植物数量：{len(self.collected_plants)}", size=14,
                                                 color=Colors.GREY_600)
                                        ],
                                        spacing=5,
                                        alignment=ft.MainAxisAlignment.CENTER,
                                        expand=True
                                    )
                                ],
                                spacing=20,
                                alignment=ft.MainAxisAlignment.CENTER
                            ),
                            Container(height=15),
                            Divider(height=15),
                            Text("个人简介", size=16, weight=ft.FontWeight.BOLD),
                            self.bio_text,
                            self.bio_field,
                            Container(height=15),
                            Divider(height=15),
                            Text("使用统计", size=16, weight=ft.FontWeight.BOLD),
                            Row(
                                controls=[
                                    Card(
                                        content=Column(
                                            controls=[
                                                Container(height=10),
                                                Text("浏览植物", size=14),
                                                Text(f"{len(self.browsing_history)}", size=20,
                                                     weight=ft.FontWeight.BOLD, color=Colors.GREEN_600),
                                                Container(height=10)
                                            ],
                                            alignment=ft.MainAxisAlignment.CENTER,
                                            spacing=5
                                        ),
                                        elevation=2
                                    ),
                                    Card(
                                        content=Column(
                                            controls=[
                                                Container(height=10),
                                                Text("收藏植物", size=14),
                                                Text(f"{len(self.collected_plants)}", size=20,
                                                     weight=ft.FontWeight.BOLD, color=Colors.GREEN_600),
                                                Container(height=10)
                                            ],
                                            alignment=ft.MainAxisAlignment.CENTER,
                                            spacing=5
                                        ),
                                        elevation=2
                                    ),
                                    Card(
                                        content=Column(
                                            controls=[
                                                Container(height=10),
                                                Text("搜索次数", size=14),
                                                Text(f"{self.user_info['searched']}", size=20,
                                                     weight=ft.FontWeight.BOLD, color=Colors.GREEN_600),
                                                Container(height=10)
                                            ],
                                            alignment=ft.MainAxisAlignment.CENTER,
                                            spacing=5
                                        ),
                                        elevation=2
                                    )
                                ],
                                spacing=15,
                                expand=True
                            ),
                            Container(height=15),
                            Divider(height=15),
                            Text("最近浏览", size=16, weight=ft.FontWeight.BOLD),
                            Container(
                                content=self.browsing_history_list,
                                height=200,
                                expand=False
                            ),
                            Container(height=15),
                            Divider(height=15),
                            Text("我的收藏", size=16, weight=ft.FontWeight.BOLD),
                            Container(
                                content=self.collection_history_list,
                                height=200,
                                expand=False
                            ),
                            Container(height=15),
                            Container(
                                content=edit_button,
                                alignment=ft.alignment.center,
                            ),
                            Container(height=20)
                        ],
                        spacing=0
                    )
                ),
                Container(height=20)
            ],
            expand=True,
            spacing=0
        )

    def on_avatar_selected(self, e: FilePickerResultEvent):
        """处理头像上传"""
        if e.files:
            file_path = e.files[0].path
            self.avatar_image.src = file_path
            self.user_info["avatar_url"] = file_path
            snack = SnackBar(Text("头像已更新"))
            self.page.snack_bar = snack
            snack.open = True
            self.page.update()

    def create_settings_page(self):
        """创建设置页"""
        return Column(
            controls=[
                Container(height=20),
                Text("设置", size=24, weight=ft.FontWeight.BOLD),
                Divider(height=20),
                Card(
                    content=Column(
                        controls=[
                            Container(height=20),
                            Text("主题设置", size=18, weight=ft.FontWeight.BOLD),
                            Row(
                                controls=[
                                    Text("浅色主题", size=14),
                                    Switch(
                                        value=self.page.theme_mode == ft.ThemeMode.LIGHT,
                                        on_change=self.toggle_theme
                                    )
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER
                            ),
                            Container(height=10),
                            Divider(height=10),
                            Container(height=10),
                            Text("通知设置", size=18, weight=ft.FontWeight.BOLD),
                            Row(
                                controls=[
                                    Text("允许通知", size=14),
                                    Switch(
                                        value=False,
                                        on_change=self.toggle_notification
                                    )
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER
                            ),
                            Container(height=10),
                            Divider(height=10),
                            Container(height=10),
                            Text("应用更新", size=18, weight=ft.FontWeight.BOLD),
                            Text("当前版本：v1.0.0", size=14, color=Colors.GREY_600),
                            Text("检查更新：已是最新版本", size=14, color=Colors.GREY_600),
                            Container(height=10),
                            Divider(height=10),
                            Container(height=10),
                            Text("关于应用", size=18, weight=ft.FontWeight.BOLD),
                            Text("「青芜识界」是一款专注于植物识别与收藏的工具，帮助您认识身边的草木。", size=14,
                                 color=Colors.GREY_700),
                            Container(height=20)
                        ],
                        spacing=0
                    )
                ),
                Container(height=20)
            ],
            expand=True,
            spacing=0
        )

    def create_notification_page(self):
        """创建通知页"""
        self.notification_list = ListView(expand=True, spacing=10)
        self.update_notification_list()
        return Column(
            controls=[
                Container(height=20),
                Text("通知中心", size=24, weight=ft.FontWeight.BOLD),
                Divider(height=20),
                self.notification_list,
                Container(height=20)
            ],
            expand=True,
            spacing=0
        )

    def update_notification_list(self):
        """更新通知列表"""
        self.notification_list.controls.clear()
        if not self.notifications:
            self.notification_list.controls.append(Text("暂无通知", color=Colors.GREY_500))
        else:
            for note in self.notifications:
                bg_color = Colors.WHITE if note["is_read"] else Colors.LIGHT_GREEN_50
                card = Card(
                    content=Container(
                        content=Column(
                            controls=[
                                Text(note["title"], weight=ft.FontWeight.BOLD),
                                Text(note["time"].strftime("%Y-%m-%d %H:%M"), size=12, color=Colors.GREY_500),
                                Text(note["content"], size=14, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS)
                            ],
                            spacing=5
                        ),
                        padding=10,
                        bgcolor=bg_color,
                        on_click=lambda e, n=note: self.navigate_to_notification_detail(n)
                    )
                )
                self.notification_list.controls.append(card)
        self.page.update()

    def navigate_to_notification_page(self):
        """跳转到通知页（标记已读）"""
        for note in self.notifications:
            if not note["is_read"]:
                note["is_read"] = True
                self.unread_count -= 1
        self.unread_count = max(0, self.unread_count)
        self.notification_badge.controls[1].visible = self.unread_count > 0
        self.badge_text.value = str(self.unread_count) if self.unread_count <= 99 else "99+"
        self.page.update()
        self.navigate_to_page(self.notification_page, "通知中心")
        self.update_notification_list()

    def navigate_to_notification_detail(self, notification):
        """跳转到通知详情页"""
        self.notification_detail_page = self.create_notification_detail_page(notification)
        self.navigate_to_page(self.notification_detail_page, f"通知：{notification['title']}")

    def create_notification_detail_page(self, notification):
        """创建通知详情页"""
        if not notification["is_read"]:
            notification["is_read"] = True
            self.unread_count = max(0, self.unread_count - 1)
            self.notification_badge.controls[1].visible = self.unread_count > 0
            self.badge_text.value = str(self.unread_count) if self.unread_count <= 99 else "99+"
        return Column(
            controls=[
                Container(height=20),
                IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    on_click=lambda _: self.navigate_to_notification_page()
                ),
                Text(notification["title"], size=20, weight=ft.FontWeight.BOLD),
                Text(notification["time"].strftime("%Y-%m-%d %H:%M"), size=12, color=Colors.GREY_500),
                Divider(height=20),
                Text(notification["content"], size=16, selectable=True),
                Container(height=20)
            ],
            expand=True,
            spacing=10
        )

    def create_welcome_notification(self):
        """创建欢迎通知"""
        welcome_content = """
        青芜拂露，草木含情。欢迎你步入「青芜识界」的草木之境。此处有龟背竹的龟纹藏着岁月的密语，栀子花的素瓣载着仲夏的诗行，多肉们把戈壁的坚韧凝为掌中萌趣。愿你在叶影婆娑中，识得每一株草木的名字，听它们讲述阳光与雨露的故事。
        """
        self.add_notification("欢迎来到青芜识界", welcome_content)

    def add_notification(self, title, content):
        """添加通知（标记未读）"""
        notification = {
            "id": len(self.notifications) + 1,
            "title": title,
            "content": content,
            "is_read": False,
            "time": datetime.datetime.now()
        }
        self.notifications.insert(0, notification)
        self.unread_count += 1
        self.notification_badge.controls[1].visible = self.unread_count > 0
        self.badge_text.value = str(self.unread_count) if self.unread_count <= 99 else "99+"
        self.page.update()

    def toggle_theme(self, e):
        """切换主题（浅色/深色）"""
        if self.page.theme_mode == ft.ThemeMode.LIGHT:
            self.page.theme_mode = ft.ThemeMode.DARK
            self.page.bgcolor = Colors.LIGHT_GREEN_900
        else:
            self.page.theme_mode = ft.ThemeMode.LIGHT
            self.page.bgcolor = Colors.LIGHT_GREEN_50
        self.page.update()

    def toggle_notification(self, e):
        """切换通知设置"""
        snack = SnackBar(Text("通知设置已更新"))
        self.page.snack_bar = snack
        snack.open = True
        self.page.update()

    def get_responsive_image_dimensions(self):
        """根据窗口宽度返回自适应图片尺寸"""
        page_width = self.page.width
        if page_width < 600:
            return 250, 188
        elif page_width < 1200:
            return 300, 225
        else:
            return 400, 300

    def on_page_resize(self, e):
        """窗口缩放时更新组件尺寸"""
        if not self.is_mobile:
            self.plant_card_width = max(150, self.page.width // 5)
        if hasattr(self, 'plant_image'):
            img_width, img_height = self.get_responsive_image_dimensions()
            self.plant_image.width = img_width
            self.plant_image.height = img_height
        self.page.update()

    def assemble_page(self):
        """组装页面布局：主体内容 + 自定义底部导航栏"""
        self.page.appbar = self.app_bar
        self.page.add(
            ft.Column(
                [
                    Container(
                        content=self.page_container,
                        expand=True,
                        alignment=alignment.top_center,
                    ),
                    self.bottom_nav,
                ],
                expand=True,
            )
        )

    def contact_support(self, e):
        """联系客服"""
        snack = SnackBar(Text("客服邮箱：support@qingwushijie.com"))
        self.page.snack_bar = snack
        snack.open = True
        self.page.update()


def main(page: Page):
    page.title = "青芜识界"
    page.padding = 0
    page.spacing = 0
    page.theme_mode = ft.ThemeMode.LIGHT

    page.theme = ft.Theme(
        color_scheme_seed=Colors.GREEN_600,
        visual_density=ft.VisualDensity.COMPACT,
    )

    page.window.min_width = 360
    page.window.min_height = 640
    page.window.width = 400
    page.window.height = 800

    app = PlantIdentifierApp(page)
    page.update()


if __name__ == "__main__":
    ft.app(
        target=main,
        view=ft.AppView.FLET_APP,
        assets_dir="assets",
        name="青芜识界"
    )