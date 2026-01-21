from django.db import models
from dataclasses import dataclass

# Create your models here.

@dataclass
class Piece:
    num: str
    color: str
    img: str
    qty: int
    name: str
