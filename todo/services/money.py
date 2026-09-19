from decimal import Decimal, ROUND_HALF_UP

def to_cents(value):
    d=Decimal(str(value).replace(',', '.'))
    if not d.is_finite():
        raise ValueError('Montant invalide')
    return int((d*100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))

def fmt(cents, currency='DH'):
    return f'{int(cents)/100:.2f} {currency}'.strip()

def rounded(value):
    return int(Decimal(str(value)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))

def allocate(total, weights):
    total=int(total)
    weights=[max(0,int(x)) for x in weights]
    base=sum(weights)
    if not base:
        return [0]*len(weights)
    values=[total*w//base for w in weights]
    order=sorted(range(len(weights)),key=lambda i: (-(total*weights[i]%base),i))
    for i in order[:total-sum(values)]:
        values[i]+=1
    return values
