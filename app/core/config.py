from dotenv import load_dotenv
import os
load_dotenv()
class Configs:
    DATABASE : str = os.getenv('DATABASE_URL')
    JWT_SECRET : str = os.getenv('JWT_SECRET')
    JWT_ALGORITHM : str = os.getenv('JWT_ALGORITHM')
    JWT_EXPIRE_MINUTES : str = os.getenv('JWT_EXPIRE_MINUTES')

    ASTERISK_WSS_URL : str = os.getenv('ASTERISK_WSS_URL')
    SIP_DOMAIN : str = os.getenv('SIP_DOMAIN')

    

configs = Configs()