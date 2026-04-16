from datetime import datetime
from typing import List, Optional

from huaqi_src.layers.data.collectors.work_data_source import WorkDataSource


class KuaishouDocsSource(WorkDataSource):
    name = "kuaishou_docs"
    source_type = "kuaishou_docs"

    def fetch_documents(self, since: Optional[datetime] = None) -> List[str]:
        return []
