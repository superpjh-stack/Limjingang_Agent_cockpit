from decimal import Decimal
from imjingang_agent import ImjingangRepository
from fastapi.testclient import TestClient
from v2.api import create_app

def test_samples_consistent_idempotent_preserve_existing(tmp_path):
    path=tmp_path/'reports.db';repo=ImjingangRepository(path)
    before=repo.all_lots()
    products=repo.table_records('report_sample_products',100)
    customers=repo.table_records('report_sample_customers',100)
    rows=repo.table_records('report_sample_production',100)
    assert len(products)==len(customers)==len(rows)==100
    codes={r['product_code']:r for r in products}; clients={r['customer_code'] for r in customers}
    for row in rows:
        assert row['is_sample']==1 and row['company']=='임진강김치'
        assert row['customer_code'] in clients
        assert row['kg_per_unit']==codes[row['product_code']]['kg_per_unit']
        for field in ['planned','good','reject']:
            assert Decimal(str(row[field+'_kg']))==Decimal(str(row['kg_per_unit']))*row[field+'_ea']
        assert row['started_at']<row['completed_at']
    with repo._connect() as connection:
        connection.execute("UPDATE report_sample_customers SET customer_name=? WHERE customer_code=?",('보존 확인','IMJ-SMP-C001'))
    repo=ImjingangRepository(path)
    assert repo.all_lots()==before
    assert len(repo.table_records('report_sample_production',100))==100
    assert repo.table_records('report_sample_customers',100)[0]['customer_name']=='보존 확인'
    with TestClient(create_app(repo)) as client:
        assert len(client.get('/api/tables/report_sample_production?limit=100').json())==100
        tables=client.get('/api/workspace').json()['tables']
        assert len([t for t in tables if t['table'].startswith('report_sample_') and t['count']==100])==3
