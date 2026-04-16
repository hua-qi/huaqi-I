from huaqi_src.layers.data.collectors.work_data_source import register_work_source
from huaqi_src.layers.data.collectors.work_sources.codeflicker import CodeflickerSource
from huaqi_src.layers.data.collectors.work_sources.huaqi_docs import HuaqiDocsSource
from huaqi_src.layers.data.collectors.work_sources.kuaishou_docs import KuaishouDocsSource


def register_defaults() -> None:
    register_work_source(CodeflickerSource())
    register_work_source(HuaqiDocsSource())
    register_work_source(KuaishouDocsSource())
