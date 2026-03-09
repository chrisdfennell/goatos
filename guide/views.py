from django.shortcuts import render
from django.http import Http404

GUIDE_PAGES = {
    'getting-started',
    'housing-fencing',
    'breeds',
    'nutrition-minerals',
    'health-vaccines-parasites',
    'hoof-care-grooming',
    'breeding-kidding',
    'bottle-feeding-kid-care',
    'security-predator-proofing',
    'behavior-training-enrichment',
    'seasonal-care',
    'checklists',
    'recordkeeping-forms',
    'common-problems-triage',
    'glossary-resources',
    'calculators',
    'barn-pack',
    'search',
    'symptom-checker',
    'fiber-goats',
    'meat-goats',
    'milking-dairy',
    'goat-milk-recipes',
    'legal-zoning',
    'poisonous-plants',
}


def guide_index(request):
    return render(request, 'guide/index.html')


def guide_page(request, slug):
    if slug not in GUIDE_PAGES:
        raise Http404
    return render(request, f'guide/{slug}.html')
