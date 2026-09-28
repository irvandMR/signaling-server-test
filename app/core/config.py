from dotenv import load_dotenv
import os
load_dotenv()

class Settings:
    HOST = os.getenv("HOST")
    PORT = int(os.getenv("PORT"))
    RUN_APP = os.getenv("RUN_APP")
    DATABASE_URL = os.getenv("DATABASE_URL")
    PBX_IP = os.getenv("PBX_IP")
    PBX_PORT = int(os.getenv("PBX_PORT"))
    

class DevelopmentSingalingServer(Settings):
    DEBUG = True

class StaggingSingalingServer(Settings):
    DEBUG = False

class ProductionSingalingServer(Settings):
    DEBUG = False

config_by_name = {
    "dev": DevelopmentSingalingServer,
    "stagging": StaggingSingalingServer,
    "production": ProductionSingalingServer,
}