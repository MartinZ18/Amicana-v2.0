import mysql.connector
passwords = ['admin', 'mysql', '1234', '12345', 'admin1234', 'password', 'root123', '', 'root', 'amicana']
for p in passwords:
    try:
        c = mysql.connector.connect(host='localhost', user='root', password=p)
        print(f"OK password: [{p}]")
        c.close()
        break
    except Exception as e:
        print(f"FAIL [{p}]: {e.msg if hasattr(e,'msg') else e}")
