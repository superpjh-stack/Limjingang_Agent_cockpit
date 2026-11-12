"""Deterministic, fictional Imjingang reporting fixtures; never overwrite records."""
from datetime import date,timedelta
from decimal import Decimal

SOURCE='임진강김치 보고서용 가상 샘플 v1 · 실제 운영자료 아님'

def seed_report_samples(connection):
    connection.executescript('''
    CREATE TABLE IF NOT EXISTS report_sample_products (
      product_code TEXT PRIMARY KEY, company TEXT NOT NULL, product_name TEXT NOT NULL,
      category TEXT NOT NULL, specification TEXT NOT NULL, kg_per_unit REAL NOT NULL,
      unit TEXT NOT NULL, origin TEXT, is_sample INTEGER NOT NULL CHECK(is_sample=1), source TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS report_sample_customers (
      customer_code TEXT PRIMARY KEY, company TEXT NOT NULL, customer_name TEXT NOT NULL,
      channel TEXT NOT NULL, region TEXT NOT NULL, delivery_method TEXT NOT NULL,
      is_sample INTEGER NOT NULL CHECK(is_sample=1), source TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS report_sample_production (
      record_id TEXT PRIMARY KEY, company TEXT NOT NULL, business_date TEXT NOT NULL,
      product_code TEXT NOT NULL REFERENCES report_sample_products(product_code),
      customer_code TEXT NOT NULL REFERENCES report_sample_customers(customer_code),
      lot_id TEXT NOT NULL UNIQUE, line_id TEXT NOT NULL, shift_id TEXT NOT NULL,
      started_at TEXT NOT NULL, completed_at TEXT NOT NULL,
      planned_ea INTEGER NOT NULL, good_ea INTEGER NOT NULL, reject_ea INTEGER NOT NULL,
      kg_per_unit REAL NOT NULL, planned_kg REAL NOT NULL, good_kg REAL NOT NULL, reject_kg REAL NOT NULL,
      status TEXT NOT NULL, is_sample INTEGER NOT NULL CHECK(is_sample=1), source TEXT NOT NULL
    );
    ''')
    names=['율무 포기김치','포기김치','맛김치','총각김치','깍두기','열무김치','백김치','동치미','갓김치','파김치']
    sizes=['0.5','0.8','1','1.5','2','2.5','3','5','10','20']
    regions=['서울','경기','인천','강원','충북','충남','전북','전남','경북','경남']
    channels=['식자재','급식','소매','온라인','외식']
    for i in range(100):
        n=i+1; code=f'IMJ-SMP-P{n:03d}'; customer=f'IMJ-SMP-C{n:03d}'
        size=Decimal(sizes[i%10]);name=names[i//10]
        connection.execute('INSERT INTO report_sample_products VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT DO NOTHING',
          (code,'임진강김치',f'임진강김치 {name} [샘플]',name,f'{size} kg/ea',float(size),'ea',None,1,SOURCE))
        connection.execute('INSERT INTO report_sample_customers VALUES (?,?,?,?,?,?,?,?) ON CONFLICT DO NOTHING',
          (customer,'임진강김치',f'가상거래처 {n:03d} · {channels[i%5]}',channels[i%5],regions[i//10],['택배','배송','방문'][i%3],1,SOURCE))
        day=date(2026,9,1)+timedelta(days=i//5);good=40+(i*17)%161;reject=i%5;plan=good+10-(i%4)*5
        kg=lambda count:float(size*count)
        connection.execute('INSERT INTO report_sample_production VALUES ('+','.join('?' for _ in range(20))+') ON CONFLICT DO NOTHING',
          (f'IMJ-SMP-R{n:03d}','임진강김치',day.isoformat(),code,customer,f'IMJ-SMP-LOT-{day:%y%m%d}-{n:03d}',f'샘플라인-{i%3+1}','주간',f'{day}T08:30:00+09:00',f'{day}T{10+i%5:02d}:30:00+09:00',plan,good,reject,float(size),kg(plan),kg(good),kg(reject),'완료(가상)',1,SOURCE))
