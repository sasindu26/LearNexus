import requests
resp = requests.post('http://localhost:8000/api/auth/profile/change-password/request', json={'old_password': 'wrong', 'new_password': 'Password123!', 'method': 'email'}, headers={'Authorization': 'Bearer ' + open('.env', 'r').read()})
print(resp.status_code, resp.text)
