# Ti6Al4V SingleTrack 模型尺寸修改说明

## 1) 当前案例的厚度是多少？

按当前输入文件定义：

- **整个 job 厚度**：`300e-6 m`（= `300 μm`）
  - 来自 `system/blockMeshDict` 的 Z 方向：`0 -> 300e-6`
- **基板厚度**：`200e-6 m`（= `200 μm`）
  - 来自 `system/bedPlateDict`：`zmin=0.0`, `zmax=0.0002`
- **粉末层厚度（几何预留）**：`100e-6 m`（= `100 μm`）
  - 计算方式：`job 厚度 - 基板厚度 = 300e-6 - 200e-6`

> 说明：当前 `constant/location` 中颗粒的实际堆积包络约为 `70 μm`（约 `z-r=199.997 μm` 到 `z+r=270.025 μm`），小于几何预留的 `100 μm`，上方存在保护气体空间。

---

## 2) 如果要改模型尺寸，需要改哪些参数？

下面按“必须改 / 可能要改”分组。

### A. CFD 几何（必须）

1. **`system/blockMeshDict`**（job 总尺寸）
   - 改 `vertices` 中的最大坐标：
     - `xmax`（如 `300e-6`）
     - `ymax`（如 `800e-6`）
     - `zmax`（如 `300e-6`，即 job 厚度）
   - 改 `blocks` 网格数 `(Nx Ny Nz)`，建议按目标网格尺寸重算：
     - `Nx ≈ Lx / cell_size`
     - `Ny ≈ Ly / cell_size`
     - `Nz ≈ Lz / cell_size`

2. **`system/bedPlateDict`**（基板范围）
   - 改 `xmin/xmax, ymin/ymax` 与 `blockMeshDict` 一致
   - 改 `zmin/zmax`，其中：
     - `zmax = 基板厚度`
   - 之后粉末几何预留厚度自动为：`job_zmax - bedPlate_zmax`

### B. 工艺路径与后处理（通常要改）

3. **`constant/timeVsLaserPosition`**（激光路径位置）
   - 轨迹点的 `x, y, z` 需要与新几何匹配
   - 尤其 `z` 通常应位于粉末层上方（或按你的工艺设定）

4. **`config.yaml`**（后处理几何参数）
   - `cell_size`
   - `x_domain`
   - `y_begin_track` / `y_end_track`
   - 否则后处理切片范围可能与新模型不一致

### C. 粉末床 / LIGGGHTS（lights）部分

本案例当前是直接读取 `constant/location` 的颗粒坐标。

5. **若只想快速改粉末厚度**
   - 直接替换 `constant/location`（新的颗粒坐标文件）
   - 关键是确保颗粒满足目标高度范围（`z-r` 到 `z+r`）

6. **若用 LIGGGHTS 重新生成粉末（推荐）**
   - 参考：`tutorials/laserbeamFoam/LPBF_large/DEM_large/input.liggghts`
   - 重点修改：
     - `region domain block ...`（DEM 计算域）
     - `region factory block ...`（投放区域）
     - `fix box` / `fix plate` 对应的 `meshes/*.stl` 尺寸
     - `variable co atom "z+c_1 > ..."`（截顶高度/保留层）
     - 若单位或缩放变更，检查 `variable x1/y1/z1` 与 `rad1` 的换算
   - 生成 `post/location` 后，拷贝为本案例的 `constant/location`

7. **STL 文件（`domain.stl` / `plate.stl`）怎么改**
   - 典型位置：`tutorials/laserbeamFoam/LPBF_large/DEM_large/meshes/`
   - 本仓库示例里这两个 STL 是**二进制 STL**，建议用 CAD/Mesh 工具修改后重新导出（不要手改二进制字节）
   - 当前示例 STL 读取结果（未缩放前）
     - `domain.stl` 包围盒：`x=[0,0.2], y=[0,0.8], z=[0,0.5]`（12 个三角面）
     - `plate.stl` 包围盒：`x=[0,0.2], y=[0,0.8], z=[0,0.1]`（12 个三角面）
     - `input.liggghts` 中当前 `scale 0.1` 后，等效尺寸分别是：
       - `domain`: `0.02 x 0.08 x 0.05`
       - `plate`:  厚度 `0.01`
   - **`domain.stl` 要改的内容**：
     - 外边界盒体的顶点坐标（`xmax, ymax, zmax`）
     - 目标是与 `input.liggghts` 中 `region domain block ...` 一致
   - **`plate.stl` 要改的内容**：
     - 基板实体（或平板）几何，重点是顶面高度和厚度
     - 目标是与 `bedPlateDict` 里的基板厚度设定一致
   - **怎么改（实操建议）**：
     - 只改厚度（最常见）：仅变换 `z` 坐标，`x/y` 不动
       - `domain.stl`：`z_new = z_old * (H_domain_new / H_domain_old)`
       - `plate.stl`： `z_new = z_old * (H_plate_new / H_plate_old)`
     - 整体改长宽高：分别对 `x/y/z` 做比例缩放，或按目标包围盒做线性映射
     - 若你保留 STL 原始尺寸不变，也可以通过 `fix ... scale` 调整；但建议 STL 与 `region` 保持同一量级，减少混淆
   - **与 `input.liggghts` 的一致性要点**：
     - `fix box ... scale ...` 与 `fix plate ... scale ...` 的 `scale` 会缩放 STL 尺寸
     - 修改 STL 尺寸后，通常也要同步检查 `region domain/factory` 和截顶阈值 `variable co`
   - **几何质量要求**：
     - 保证 STL 闭合（watertight）
     - 法向方向一致（建议外法向）
     - 无自交、无退化三角面
   - **最小检查清单**：
     - `domain.stl` 的包围盒尺寸 == DEM 目标域尺寸
     - `plate.stl` 的顶面高度 == 目标基板高度
     - 生成后的 `constant/location` 颗粒高度分布落在目标粉末层范围内

---

## 3) 推荐修改流程（最稳妥）

1. 先改 `blockMeshDict`（总尺寸）+ `bedPlateDict`（基板尺寸）
2. 再改 `timeVsLaserPosition` 与 `config.yaml`（路径/后处理）
3. 再更新 `constant/location`（或从 LIGGGHTS 重生）
4. 重新执行：

```bash
blockMesh
setSolidFraction
```

5. 用以下命令快速检查粉末实际厚度（基于 `location`）：

```bash
awk 'BEGIN{min=1e9;max=-1e9;start=0} /^ITEM: ATOMS/{start=1;next} start&&NF>=4{z=$3;r=$4;if(z-r<min)min=z-r;if(z+r>max)max=z+r} END{printf("z-r min=%.9g, z+r max=%.9g, thickness=%.9g\n",min,max,max-min)}' constant/location
```
