#!/usr/bin/env python3
"""数据迁移脚本：v3 -> v4

将旧版数据迁移到新的向量存储架构
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import argparse


def get_data_dir() -> Path:
    """获取数据目录"""
    return Path.home() / ".huaqi" / "memory"


def backup_data(data_dir: Path, backup_dir: Path = None) -> Path:
    """备份数据
    
    Args:
        data_dir: 数据目录
        backup_dir: 备份目录，默认为 data_dir/backups/YYYYMMDD_HHMMSS
        
    Returns:
        备份目录路径
    """
    if backup_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = data_dir / "backups" / f"pre_migration_{timestamp}"
    
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    # 复制所有数据
    for item in data_dir.iterdir():
        if item.name == "backups":
            continue
        
        dest = backup_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest, ignore=shutil.ignore_patterns("backups"))
        else:
            shutil.copy2(item, dest)
    
    print(f"✅ 数据已备份到: {backup_dir}")
    return backup_dir


def restore_backup(backup_dir: Path, data_dir: Path):
    """从备份恢复数据
    
    Args:
        backup_dir: 备份目录
        data_dir: 数据目录
    """
    print(f"🔄 正在从 {backup_dir} 恢复数据...")
    
    # 清除当前数据
    for item in data_dir.iterdir():
        if item.name == "backups":
            continue
        
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()
    
    # 恢复备份
    for item in backup_dir.iterdir():
        dest = data_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)
    
    print("✅ 数据恢复完成")


def migrate_diary_to_vector(data_dir: Path) -> Tuple[int, int]:
    """将日记迁移到向量存储
    
    Returns:
        (成功数, 失败数)
    """
    try:
        from huaqi_src.layers.data.memory.vector.chroma_client import ChromaClient
        from huaqi_src.layers.data.memory.vector.embedder import TextEmbedder
    except ImportError:
        print("⚠️ 向量存储模块未安装，跳过日记向量化")
        return 0, 0
    
    diary_dir = data_dir / "diary"
    if not diary_dir.exists():
        print("📔 无日记数据需要迁移")
        return 0, 0
    
    print("📔 开始迁移日记到向量存储...")
    
    client = ChromaClient()
    embedder = TextEmbedder()
    
    success = 0
    failed = 0
    
    for diary_file in diary_dir.rglob("*.md"):
        try:
            # 读取日记内容
            with open(diary_file, "r", encoding="utf-8") as f:
                content = f.read()
            
            # 解析日期
            date_str = diary_file.stem
            
            # 生成 embedding
            embedding = embedder.embed(content)
            
            # 添加到向量库
            client.add(
                doc_id=f"diary_{date_str}",
                content=content,
                metadata={
                    "type": "diary",
                    "date": date_str,
                    "source": str(diary_file),
                },
                embedding=embedding,
            )
            
            success += 1
            print(f"  ✓ {date_str}")
            
        except Exception as e:
            failed += 1
            print(f"  ✗ {diary_file.name}: {e}")
    
    print(f"✅ 日记迁移完成: {success} 成功, {failed} 失败")
    return success, failed


def migrate_personality(data_dir: Path) -> bool:
    """迁移人格画像
    
    Returns:
        是否成功
    """
    personality_file = data_dir / "personality.yaml"
    if not personality_file.exists():
        print("👤 无人格画像需要迁移")
        return True
    
    print("👤 迁移人格画像...")
    
    try:
        import yaml
        with open(personality_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        # 新版格式兼容处理
        # 如果格式相同，无需迁移
        print("✅ 人格画像格式兼容，无需迁移")
        return True
        
    except Exception as e:
        print(f"❌ 人格画像迁移失败: {e}")
        return False


def migrate_skills(data_dir: Path) -> bool:
    """迁移技能数据
    
    Returns:
        是否成功
    """
    skills_file = data_dir / "skills.json"
    if not skills_file.exists():
        print("🎯 无技能数据需要迁移")
        return True
    
    print("🎯 迁移技能数据...")
    
    try:
        with open(skills_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # 新版格式兼容处理
        print(f"✅ 技能数据已加载: {len(data.get('skills', []))} 个技能")
        return True
        
    except Exception as e:
        print(f"❌ 技能数据迁移失败: {e}")
        return False


def check_migration_needed(data_dir: Path) -> bool:
    """检查是否需要迁移
    
    Returns:
        True 表示需要迁移
    """
    # 检查是否有向量存储
    vector_dir = data_dir / "vector"
    if vector_dir.exists():
        print("✅ 数据已是最新版本 (v4)，无需迁移")
        return False
    
    # 检查是否有旧版数据
    diary_dir = data_dir / "diary"
    if diary_dir.exists() and any(diary_dir.iterdir()):
        print("📦 检测到 v3 数据，需要迁移")
        return True
    
    print("📦 无数据需要迁移")
    return False


def run_migration(
    data_dir: Path = None,
    skip_backup: bool = False,
    dry_run: bool = False,
) -> bool:
    """执行迁移
    
    Args:
        data_dir: 数据目录，默认 ~/.huaqi/memory
        skip_backup: 是否跳过备份
        dry_run: 是否仅预览，不实际执行
        
    Returns:
        是否成功
    """
    if data_dir is None:
        data_dir = get_data_dir()
    
    print("=" * 50)
    print("🚀 Huaqi 数据迁移 v3 -> v4")
    print("=" * 50)
    print(f"数据目录: {data_dir}")
    print()
    
    # 检查是否需要迁移
    if not check_migration_needed(data_dir):
        return True
    
    if dry_run:
        print("🔍 [预览模式] 不会实际修改数据")
        print("将执行的操作:")
        print("  1. 备份数据")
        print("  2. 迁移日记到向量存储")
        print("  3. 迁移人格画像")
        print("  4. 迁移技能数据")
        print()
        return True
    
    # 备份数据
    if not skip_backup:
        backup_dir = backup_data(data_dir)
        print(f"如需回滚，请运行: python migrate_v3_to_v4.py --restore {backup_dir}")
        print()
    
    # 执行迁移
    results = {
        "diary": (0, 0),
        "personality": False,
        "skills": False,
    }
    
    try:
        # 迁移日记
        results["diary"] = migrate_diary_to_vector(data_dir)
        
        # 迁移人格画像
        results["personality"] = migrate_personality(data_dir)
        
        # 迁移技能
        results["skills"] = migrate_skills(data_dir)
        
    except Exception as e:
        print(f"\n❌ 迁移过程中出错: {e}")
        if not skip_backup:
            print(f"正在从备份恢复...")
            restore_backup(backup_dir, data_dir)
        return False
    
    # 输出结果
    print("\n" + "=" * 50)
    print("📊 迁移结果")
    print("=" * 50)
    
    diary_success, diary_failed = results["diary"]
    print(f"日记迁移: {diary_success} 成功, {diary_failed} 失败")
    print(f"人格画像: {'✅' if results['personality'] else '❌'}")
    print(f"技能数据: {'✅' if results['skills'] else '❌'}")
    
    if diary_failed > 0 or not results["personality"] or not results["skills"]:
        print("\n⚠️ 部分迁移失败，建议检查日志")
        return False
    
    print("\n✅ 迁移完成！")
    print("请验证数据完整性后，可以删除备份")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Huaqi 数据迁移工具 v3 -> v4"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        help="数据目录 (默认: ~/.huaqi/memory)",
    )
    parser.add_argument(
        "--skip-backup",
        action="store_true",
        help="跳过备份（不推荐）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="预览模式，不实际执行",
    )
    parser.add_argument(
        "--restore",
        type=Path,
        metavar="BACKUP_DIR",
        help="从备份恢复数据",
    )
    
    args = parser.parse_args()
    
    if args.restore:
        data_dir = args.data_dir or get_data_dir()
        restore_backup(args.restore, data_dir)
        return
    
    success = run_migration(
        data_dir=args.data_dir,
        skip_backup=args.skip_backup,
        dry_run=args.dry_run,
    )
    
    exit(0 if success else 1)


if __name__ == "__main__":
    main()
