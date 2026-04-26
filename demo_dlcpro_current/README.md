# DLC pro 电流控制 Demo

这是一个独立于主项目的小型演示程序，目标是基于 TOOPTICA 官方
`toptica.lasersdk.dlcpro.v2_6_0` 高层接口，实现一个最小但完整的中文 GUI：

- 连接 DLC pro 设备
- 显示设备基础信息
- 显示单一电流值
- 用键盘上下键和数值框精细调节电流值

该 Demo 不依赖字符串拼接来“猜”参数路径，而是直接使用官方 SDK 源码中确认过的高层对象树：

- `dlc.system_type`
- `dlc.serial_number`
- `dlc.system_label`
- `dlc.uptime_txt`
- `dlc.laser1.dl.cc.enabled`
- `dlc.laser1.dl.cc.emission`
- `dlc.laser1.dl.cc.current_set`
- `dlc.laser1.dl.cc.current_act`

## 运行

```bash
cd /Users/YieFanMeng/Desktop/Toptica_v1
python3 demo_dlcpro_current/app.py
```

如果你使用 conda 环境：

```bash
cd /Users/YieFanMeng/Desktop/Toptica_v1
conda run -n toptica-lab python demo_dlcpro_current/app.py
```

## 注意

- 默认提供 `Demo 模式`，没有真机时也能启动界面。
- 真机模式下默认使用网络连接。
- 该 Demo 当前只演示电流读取与电流写入，不包含高风险控制逻辑的全面防护。
- 真实设备上调电流前，请先确认老师允许的安全范围。
