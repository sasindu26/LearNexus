import os
import requests
import json
os.environ['GREEN_API_URL'] = 'https://7107.api.greenapi.com'
os.environ['GREEN_API_ID'] = '7107614787'
os.environ['GREEN_API_TOKEN'] = 'e8a7b80952044ab6b98280724ad10354481d389dafe04f3f91'
from api.services.whatsapp_service import send_whatsapp
res = send_whatsapp('94742439381', 'test msg')
print('Success:', res)
