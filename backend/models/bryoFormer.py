import math
import logging
from functools import partial
from collections import OrderedDict
from copy import Error, deepcopy
from re import S
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from timm.data import IMAGENET_DEFAULT_MEAN, IMAGENET_DEFAULT_STD
from timm.layers import DropPath, to_2tuple, trunc_normal_
import torch.fft
from timm.models import register_model
from torch.nn.modules.container import Sequential

_logger = logging.getLogger(__name__)


def _cfg(url='', **kwargs):
    return {
        'url': url,
        'num_classes': 1000, 'input_size': (3, 224, 224), 'pool_size': None,
        'crop_pct': .9, 'interpolation': 'bicubic',
        'mean': IMAGENET_DEFAULT_MEAN, 'std': IMAGENET_DEFAULT_STD,
        'first_conv': 'patch_embed.proj', 'classifier': 'head',
        **kwargs
    }

class SpectralGatingNetwork(nn.Module):
    def __init__(self, dim, h=14, w=8):
        super().__init__()
        self.complex_weight = nn.Parameter(torch.randn(h, w, dim, 2, dtype=torch.float32) * 0.02)
        self.w = w
        self.h = h

    def forward(self, x, spatial_size=None):
        B, N, C = x.shape
        if spatial_size is None:
            a = b = int(math.sqrt(N))
        else:
            a, b = spatial_size
        x = x.view(B, a, b, C)
        x = x.to(torch.float32)
        x = torch.fft.rfft2(x, dim=(1, 2), norm='ortho')
        weight = torch.view_as_complex(self.complex_weight)
        x = x * weight
        x = torch.fft.irfft2(x, s=(a, b), dim=(1, 2), norm='ortho')
        x = x.reshape(B, N, C)
        return x


class ChannelAttention(nn.Module):
    def __init__(self, in_channels, reduction=4):
        super().__init__()
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.conv_reduce = nn.Conv2d(in_channels, in_channels // reduction,
                                     kernel_size=1, groups=in_channels // reduction)
        self.act = nn.ReLU(inplace=True)
        self.conv_expand = nn.Conv2d(in_channels // reduction, in_channels,
                                     kernel_size=1)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        y = self.avg_pool(x)
        y = self.conv_reduce(y)
        y = self.act(y)
        y = self.conv_expand(y)
        return x * self.sigmoid(y)


class SpatialAttention(nn.Module):
    def __init__(self, in_channels, kernel_size=3):
        super().__init__()
        # 空间特征提取
        self.dw_conv = nn.Conv2d(in_channels, in_channels, kernel_size,
                                 padding=kernel_size // 2, groups=in_channels)
        self.bn = nn.BatchNorm2d(in_channels)
        # 注意力生成
        self.conv_att = nn.Conv2d(2, 1, kernel_size=3, padding=1, bias=False)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        x = self.bn(self.dw_conv(x))
        avg_out = torch.mean(x, dim=1, keepdim=True)  # [B,1,H,W]
        max_out, _ = torch.max(x, dim=1, keepdim=True)
        att = self.conv_att(torch.cat([avg_out, max_out], dim=1))
        return x * self.sigmoid(att)


class FeatureFusion(nn.Module):
    def __init__(self, in_channels):
        super().__init__()
        # 拼接后通道数变为 2*in_channels，用 1x1 卷积降回 in_channels
        self.conv_fusion = nn.Sequential(
            nn.Conv2d(2 * in_channels, in_channels, kernel_size=1),
            nn.BatchNorm2d(in_channels),
            nn.ReLU(inplace=True)
        )

    def forward(self, x, channel_feat, spatial_feat):
        fused = torch.cat([channel_feat, spatial_feat], dim=1)
        return self.conv_fusion(fused)


class AttentionModule(nn.Module):
    def __init__(self, in_channels, channel_reduction=4, spatial_ksize=3):
        super().__init__()
        self.channel_att = ChannelAttention(in_channels, channel_reduction)
        self.spatial_att = SpatialAttention(in_channels, spatial_ksize)
        self.fusion = FeatureFusion(in_channels)

    def forward(self, x):
        channel_out = self.channel_att(x)
        spatial_out = self.spatial_att(x)
        return self.fusion(x, channel_out, spatial_out)


class FreqTimeBridge(nn.Module):
    def __init__(self, dim, h=14, w=8):
        super().__init__()
        # 频域处理
        self.spectral = SpectralGatingNetwork(dim, h, w)
        self.norm = nn.LayerNorm(dim)
        # 注意力处理
        self.attn_module = AttentionModule(in_channels=dim)
        # 输出处理
        self.proj = nn.Linear(dim, dim)
        self.alpha = nn.Parameter(torch.tensor(0.5))  # 控制残差强度

    def forward(self, x):
        B, N, C = x.shape
        H = W = int(math.sqrt(N))
        # 第一步：频域增强
        x_norm = self.norm(x)  # 层归一化
        x_freq = self.spectral(x_norm)  # 频域滤波 [B,N,C]
        # 第二步：转换为2D并处理注意力
        x_2d = x_freq.transpose(1, 2).view(B, C, H, W)  # [B,C,H,W]
        x_attn = self.attn_module(x_2d)  # 并行通道+空间注意力
        # 第三步：恢复序列格式并残差输出
        x_fused = x_attn.flatten(2).transpose(1, 2)  # [B,N,C]
        return x + self.proj(x_fused) * self.alpha.sigmoid()


class Block(nn.Module):
    def __init__(self, dim, mlp_ratio=4., drop=0., drop_path=0., act_layer=nn.GELU, norm_layer=nn.LayerNorm, h=14, w=8):
        super().__init__()
        self.norm1 = norm_layer(dim)
        self.filter = SpectralGatingNetwork(dim, h=h, w=w)
        self.drop_path = DropPath(drop_path) if drop_path > 0. else nn.Identity()
        self.norm2 = norm_layer(dim)
        mlp_hidden_dim = int(dim * mlp_ratio)
        self.mlp = Mlp(in_features=dim, hidden_features=mlp_hidden_dim, act_layer=act_layer, drop=drop)

    def forward(self, x):
        x = x + self.drop_path(self.mlp(self.norm2(self.filter(self.norm1(x)))))
        return x


class Block_attention(nn.Module):
    def __init__(self, dim, mlp_ratio=4., drop=0., drop_path=0., act_layer=nn.GELU, norm_layer=nn.LayerNorm, h=14, w=8):
        super().__init__()
        self.norm1 = norm_layer(dim)
        self.drop_path = DropPath(drop_path) if drop_path > 0. else nn.Identity()
        self.norm2 = norm_layer(dim)
        mlp_hidden_dim = int(dim * mlp_ratio)
        self.mlp = Mlp(in_features=dim, hidden_features=mlp_hidden_dim, act_layer=act_layer, drop=drop)
        self.attn = OSRAttention(dim=dim, num_heads=6, qk_scale=None, attn_drop=drop, sr_ratio=2)

    def forward(self, x):
        B, N, C = x.shape
        H = W = int(math.sqrt(N))
        x_2d = x.transpose(1, 2).view(B, C, H, W)
        attn_out = self.attn(x_2d).view(B, C, N).transpose(1, 2)
        x = x + self.drop_path(attn_out)
        x = x + self.drop_path(self.mlp(self.norm2(x)))
        return x


class OSRAttention(nn.Module):
    def __init__(self, dim, num_heads=8, qk_scale=None, attn_drop=0., sr_ratio=2):
        super().__init__()
        assert dim % num_heads == 0, f"dim {dim} should be divided by num_heads {num_heads}."
        self.dim = dim
        self.num_heads = num_heads
        head_dim = dim // num_heads
        self.scale = qk_scale or head_dim ** -0.5
        self.sr_ratio = sr_ratio

        self.q = nn.Conv2d(dim, dim, kernel_size=1)
        self.kv = nn.Conv2d(dim, dim * 2, kernel_size=1)
        self.attn_drop = nn.Dropout(attn_drop)

        if sr_ratio > 1:
            self.sr = nn.Sequential(
                nn.AvgPool2d(kernel_size=sr_ratio, stride=sr_ratio, padding=0),
                nn.Conv2d(dim, dim, kernel_size=3, padding=1, groups=dim, bias=False),
                nn.BatchNorm2d(dim),
                nn.ReLU(),
                nn.Conv2d(dim, dim, kernel_size=1, groups=dim, bias=False),
                nn.BatchNorm2d(dim),
            )
        else:
            self.sr = nn.Identity()

        self.local_conv = nn.Conv2d(dim, dim, kernel_size=3, padding=1, groups=dim)

    def forward(self, x, relative_pos_enc=None):
        B, C, H, W = x.shape
        q = self.q(x).reshape(B, self.num_heads, C // self.num_heads, -1).transpose(-1, -2)
        kv = self.sr(x)
        kv = self.local_conv(kv) + kv
        k, v = torch.chunk(self.kv(kv), chunks=2, dim=1)
        k = k.reshape(B, self.num_heads, C // self.num_heads, -1)
        v = v.reshape(B, self.num_heads, C // self.num_heads, -1).transpose(-1, -2)
        attn = (q @ k) * self.scale
        if relative_pos_enc is not None:
            if attn.shape[2:] != relative_pos_enc.shape[2:]:
                relative_pos_enc = F.interpolate(relative_pos_enc, size=attn.shape[2:], mode='bicubic',
                                                 align_corners=False)
            attn = attn + relative_pos_enc
        attn = torch.softmax(attn, dim=-1)
        attn = self.attn_drop(attn)
        x = (attn @ v).transpose(-1, -2)
        return x.reshape(B, C, H, W)


class Mlp(nn.Module):
    def __init__(self, in_features, hidden_features=None, out_features=None, act_layer=nn.GELU, drop=0.):
        super().__init__()
        out_features = out_features or in_features
        hidden_features = hidden_features or in_features
        self.fc1 = nn.Linear(in_features, hidden_features)
        self.act = act_layer()
        self.fc2 = nn.Linear(hidden_features, out_features)
        self.drop = nn.Dropout(drop)

    def forward(self, x):
        x = self.fc1(x)
        x = self.act(x)
        x = self.drop(x)
        x = self.fc2(x)
        x = self.drop(x)
        return x


class PatchEmbed(nn.Module):
    def __init__(self, img_size=224, patch_size=16, in_chans=3, embed_dim=768):
        super().__init__()
        img_size = to_2tuple(img_size)
        patch_size = to_2tuple(patch_size)
        num_patches = (img_size[1] // patch_size[1]) * (img_size[0] // patch_size[0])
        self.img_size = img_size
        self.patch_size = patch_size
        self.num_patches = num_patches

        self.stage1 = nn.Sequential(
            nn.Conv2d(in_chans, embed_dim // 8, kernel_size=3, stride=2, padding=1),
            nn.GELU()
        )

        self.stage2 = nn.Sequential(
            nn.Conv2d(embed_dim // 8, embed_dim // 8, kernel_size=8, stride=8, groups=embed_dim // 8, padding=0),
            nn.Conv2d(embed_dim // 8, embed_dim, kernel_size=1, stride=1)
        )

    def forward(self, x):
        B, C, H, W = x.shape
        assert H == self.img_size[0] and W == self.img_size[1], \
            f"Input image size ({H}*{W}) doesn't match model ({self.img_size[0]}*{self.img_size[1]})."
        x = self.stage1(x)
        x = self.stage2(x)
        x = x.flatten(2).transpose(1, 2)
        return x


class BryoFormer(nn.Module):
    def __init__(self, img_size=224, patch_size=16, in_chans=3, num_classes=44, embed_dim=384, depth=8,
                 mlp_ratio=2., representation_size=None, uniform_drop=False,
                 drop_rate=0., drop_path_rate=0., norm_layer=None, dropcls=0):
        super().__init__()
        self.num_classes = num_classes
        self.num_features = self.embed_dim = embed_dim
        norm_layer = norm_layer or partial(nn.LayerNorm, eps=1e-6)

        self.patch_embed = PatchEmbed(img_size=img_size, patch_size=patch_size, in_chans=in_chans, embed_dim=embed_dim)
        num_patches = self.patch_embed.num_patches

        self.pos_embed = nn.Parameter(torch.zeros(1, num_patches, embed_dim))
        self.pos_drop = nn.Dropout(p=drop_rate)

        h = img_size // patch_size
        w = h // 2 + 1

        if uniform_drop:
            dpr = [drop_path_rate for _ in range(depth)]
        else:
            dpr = [x.item() for x in torch.linspace(0, drop_path_rate, depth)]

        self.blocks = nn.ModuleList()
        for i in range(4):
            self.blocks.append(Block(dim=embed_dim, mlp_ratio=mlp_ratio, drop=drop_rate, drop_path=dpr[i],
                                     norm_layer=norm_layer, h=h, w=w))

        self.blocks.append(FreqTimeBridge(dim=embed_dim, h=h, w=w))

        for i in range(5, depth):
            self.blocks.append(Block_attention(dim=embed_dim, mlp_ratio=mlp_ratio, drop=drop_rate, drop_path=dpr[i],
                                               norm_layer=norm_layer, h=h, w=w))

        self.norm = norm_layer(embed_dim)
        if representation_size:
            self.pre_logits = nn.Sequential(OrderedDict([
                ('fc', nn.Linear(embed_dim, representation_size)),
                ('act', nn.Tanh())
            ]))
        else:
            self.pre_logits = nn.Identity()

        self.head = nn.Linear(self.num_features, num_classes) if num_classes > 0 else nn.Identity()
        if dropcls > 0:
            self.final_dropout = nn.Dropout(p=dropcls)
        else:
            self.final_dropout = nn.Identity()

        trunc_normal_(self.pos_embed, std=.02)
        self.apply(self._init_weights)

    def _init_weights(self, m):
        if isinstance(m, nn.Linear):
            trunc_normal_(m.weight, std=.02)
            if isinstance(m, nn.Linear) and m.bias is not None:
                nn.init.constant_(m.bias, 0)
        elif isinstance(m, nn.LayerNorm):
            nn.init.constant_(m.bias, 0)
            nn.init.constant_(m.weight, 1.0)

    def forward_features(self, x):
        B = x.shape[0]
        x = self.patch_embed(x)
        x = x + self.pos_embed
        x = self.pos_drop(x)

        for blk in self.blocks:
            x = blk(x)

        x = self.norm(x).mean(1)
        return x

    def forward(self, x):
        x = self.forward_features(x)
        x = self.final_dropout(x)
        x = self.head(x)
        return x


class BryoFormerV2(nn.Module):
    def __init__(self, img_size=224, patch_size=16, in_chans=3, num_classes=1000, embed_dim=384, depth=8,
                 mlp_ratio=4., representation_size=None, uniform_drop=False,
                 drop_rate=0., drop_path_rate=0., norm_layer=None, dropcls=0):
        super().__init__()
        # 复用原始配置
        self.base_model = BryoFormer(
            img_size=img_size,
            patch_size=patch_size,
            in_chans=in_chans,
            num_classes=num_classes,
            embed_dim=embed_dim,
            depth=depth,
            mlp_ratio=mlp_ratio,
            representation_size=representation_size,
            uniform_drop=uniform_drop,
            drop_rate=drop_rate,
            drop_path_rate=drop_path_rate,
            norm_layer=norm_layer,
            dropcls=dropcls
        )

        # 重新构建blocks
        h = img_size // patch_size
        w = h // 2 + 1

        if uniform_drop:
            dpr = [drop_path_rate for _ in range(depth)]
        else:
            dpr = [x.item() for x in torch.linspace(0, drop_path_rate, depth)]

        new_blocks = nn.ModuleList([
            # 阶段1：频域处理（3层）
            *[Block(dim=embed_dim,
                    mlp_ratio=mlp_ratio,
                    drop=drop_rate,
                    drop_path=dpr[i],
                    norm_layer=norm_layer or partial(nn.LayerNorm, eps=1e-6),
                    h=h, w=w) for i in range(3)],

            # 阶段2：桥接层（1层）
            FreqTimeBridge(dim=embed_dim, h=h, w=w),

            # 阶段3：注意力处理（8层）
            *[Block_attention(dim=embed_dim,
                              mlp_ratio=mlp_ratio,
                              drop=drop_rate,
                              drop_path=dpr[i + 4],  # 注意索引偏移
                              norm_layer=norm_layer or partial(nn.LayerNorm, eps=1e-6),
                              h=h, w=w) for i in range(4)]
        ])
        self.base_model.blocks = new_blocks

    def forward(self, x):
        return self.base_model(x)

    class BryoFormerV3(nn.Module):

        def __init__(self, img_size=224, patch_size=16, in_chans=3, num_classes=1000, embed_dim=768, depth=12,
                     mlp_ratio=4., representation_size=None, uniform_drop=False,
                     drop_rate=0., drop_path_rate=0., norm_layer=None, dropcls=0):
            super().__init__()
            self.base_model = BryoFormer(
                img_size=img_size,
                patch_size=patch_size,
                in_chans=in_chans,
                num_classes=num_classes,
                embed_dim=embed_dim,
                depth=depth,
                mlp_ratio=mlp_ratio,
                representation_size=representation_size,
                uniform_drop=uniform_drop,
                drop_rate=drop_rate,
                drop_path_rate=drop_path_rate,
                norm_layer=norm_layer,
                dropcls=dropcls
            )

            h = img_size // patch_size
            w = h // 2 + 1

            if uniform_drop:
                dpr = [drop_path_rate for _ in range(depth)]
            else:
                dpr = [x.item() for x in torch.linspace(0, drop_path_rate, depth)]

            new_blocks = nn.ModuleList([
                # 阶段1：频域处理（2层）
                *[Block(dim=embed_dim,
                        mlp_ratio=mlp_ratio,
                        drop=drop_rate,
                        drop_path=dpr[i],
                        norm_layer=norm_layer or partial(nn.LayerNorm, eps=1e-6),
                        h=h, w=w) for i in range(2)],

                # 阶段2：桥接层（2层）
                *[FreqTimeBridge(dim=embed_dim, h=h, w=w) for _ in range(2)],

                # 阶段3：注意力处理（8层）
                *[Block_attention(dim=embed_dim,
                                  mlp_ratio=mlp_ratio,
                                  drop=drop_rate,
                                  drop_path=dpr[i + 4],
                                  norm_layer=norm_layer or partial(nn.LayerNorm, eps=1e-6),
                                  h=h, w=w) for i in range(8)]
            ])
            self.base_model.blocks = new_blocks

        def forward(self, x):
            return self.base_model(x)

    class BryoFormerV4(nn.Module):

        def __init__(self, img_size=224, patch_size=16, in_chans=3, num_classes=1000, embed_dim=768, depth=12,
                     mlp_ratio=4., representation_size=None, uniform_drop=False,
                     drop_rate=0., drop_path_rate=0., norm_layer=None, dropcls=0):
            super().__init__()
            self.base_model = BryoFormer(
                img_size=img_size,
                patch_size=patch_size,
                in_chans=in_chans,
                num_classes=num_classes,
                embed_dim=embed_dim,
                depth=depth,
                mlp_ratio=mlp_ratio,
                representation_size=representation_size,
                uniform_drop=uniform_drop,
                drop_rate=drop_rate,
                drop_path_rate=drop_path_rate,
                norm_layer=norm_layer,
                dropcls=dropcls
            )

            h = img_size // patch_size
            w = h // 2 + 1

            if uniform_drop:
                dpr = [drop_path_rate for _ in range(depth)]
            else:
                dpr = [x.item() for x in torch.linspace(0, drop_path_rate, depth)]

            new_blocks = nn.ModuleList([
                # 阶段1：频域处理（3层）
                *[Block(dim=embed_dim,
                        mlp_ratio=mlp_ratio,
                        drop=drop_rate,
                        drop_path=dpr[i],
                        norm_layer=norm_layer or partial(nn.LayerNorm, eps=1e-6),
                        h=h, w=w) for i in range(3)],

                # 阶段2：直接连接注意力层（9层）
                *[Block_attention(dim=embed_dim,
                                  mlp_ratio=mlp_ratio,
                                  drop=drop_rate,
                                  drop_path=dpr[i + 3],
                                  norm_layer=norm_layer or partial(nn.LayerNorm, eps=1e-6),
                                  h=h, w=w) for i in range(9)]
            ])
            self.base_model.blocks = new_blocks

        def forward(self, x):
            return self.base_model(x)


def to_2tuple(x):
    return (x, x) if isinstance(x, int) else x


def resize_pos_embed(posemb, posemb_new):
    _logger.info('Resized position embedding: %s to %s', posemb.shape, posemb_new.shape)
    ntok_new = posemb_new.shape[1]
    posemb_tok, posemb_grid = posemb[:, :1], posemb[0, 1:]
    gs_old = int(math.sqrt(len(posemb_grid)))
    gs_new = int(math.sqrt(ntok_new))
    _logger.info('Position embedding grid-size from %s to %s', gs_old, gs_new)
    posemb_grid = posemb_grid.reshape(1, gs_old, gs_old, -1).permute(0, 3, 1, 2)
    posemb_grid = F.interpolate(posemb_grid, size=(gs_new, gs_new), mode='bilinear')
    posemb_grid = posemb_grid.permute(0, 2, 3, 1).reshape(1, gs_new * gs_new, -1)
    return torch.cat([posemb_tok, posemb_grid], dim=1)


def checkpoint_filter_fn(state_dict, model):
    out_dict = {}
    if 'model' in state_dict:
        state_dict = state_dict['model']
    for k, v in state_dict.items():
        if 'patch_embed.proj.weight' in k and len(v.shape) < 4:
            O, I, H, W = model.patch_embed.proj.weight.shape
            v = v.reshape(O, -1, H, W)
        elif k == 'pos_embed' and v.shape != model.pos_embed.shape:
            v = resize_pos_embed(v, model.pos_embed)
        out_dict[k] = v
    return out_dict