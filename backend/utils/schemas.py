from dataclasses import dataclass


@dataclass
class Chunk:
  index: int
  content: str
  section_id: str
  level: str
  parent_id: str
  parent_title: str
  metadata: dict