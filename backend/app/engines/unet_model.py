"""A deliberately small U-Net for Sentinel-2 change detection. Input is a
stacked (before bands + after bands + index differences) tensor; output is
a per-pixel change probability. Kept small (base width 16, 4 levels, ~1.9M
params) so it trains in a reasonable time on a laptop (MPS or CPU)."""
import torch
from torch import nn


def _conv_block(in_ch: int, out_ch: int) -> nn.Sequential:
    return nn.Sequential(
        nn.Conv2d(in_ch, out_ch, 3, padding=1),
        nn.BatchNorm2d(out_ch),
        nn.ReLU(inplace=True),
        nn.Conv2d(out_ch, out_ch, 3, padding=1),
        nn.BatchNorm2d(out_ch),
        nn.ReLU(inplace=True),
    )


class SmallUNet(nn.Module):
    def __init__(self, in_channels: int, base_width: int = 16):
        super().__init__()
        w = base_width
        self.enc1 = _conv_block(in_channels, w)
        self.enc2 = _conv_block(w, w * 2)
        self.enc3 = _conv_block(w * 2, w * 4)
        self.enc4 = _conv_block(w * 4, w * 8)
        self.pool = nn.MaxPool2d(2)

        self.bottleneck = _conv_block(w * 8, w * 16)

        self.up4 = nn.ConvTranspose2d(w * 16, w * 8, 2, stride=2)
        self.dec4 = _conv_block(w * 16, w * 8)
        self.up3 = nn.ConvTranspose2d(w * 8, w * 4, 2, stride=2)
        self.dec3 = _conv_block(w * 8, w * 4)
        self.up2 = nn.ConvTranspose2d(w * 4, w * 2, 2, stride=2)
        self.dec2 = _conv_block(w * 4, w * 2)
        self.up1 = nn.ConvTranspose2d(w * 2, w, 2, stride=2)
        self.dec1 = _conv_block(w * 2, w)

        self.out_conv = nn.Conv2d(w, 1, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        e1 = self.enc1(x)
        e2 = self.enc2(self.pool(e1))
        e3 = self.enc3(self.pool(e2))
        e4 = self.enc4(self.pool(e3))
        b = self.bottleneck(self.pool(e4))

        d4 = self.dec4(torch.cat([self.up4(b), e4], dim=1))
        d3 = self.dec3(torch.cat([self.up3(d4), e3], dim=1))
        d2 = self.dec2(torch.cat([self.up2(d3), e2], dim=1))
        d1 = self.dec1(torch.cat([self.up1(d2), e1], dim=1))

        return torch.sigmoid(self.out_conv(d1))


def count_params(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters())
