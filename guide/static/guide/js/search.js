/* Site-wide search — client-side, index loaded once */
(function () {
    const PAGES = [
        { url: "/guide/getting-started", title: "Getting Started", keywords: "beginner first goat buying setup planning how many goats herd starter tips" },
        { url: "/guide/housing-fencing", title: "Housing & Fencing", keywords: "shelter barn pen fencing wire pasture rotation bedding ventilation three-sided space requirements electric fence cattle panel" },
        { url: "/guide/breeds", title: "Breeds & Choosing", keywords: "Nigerian Dwarf Nubian Boer LaMancha Alpine Saanen Pygmy Kiko dairy meat fiber pet breed selection" },
        { url: "/guide/nutrition-minerals", title: "Nutrition & Minerals", keywords: "hay forage alfalfa grain feed minerals copper selenium zinc loose mineral salt baking soda water bolus COWP wethers urinary calculi" },
        { url: "/guide/health-vaccines-parasites", title: "Vaccines & Parasites", keywords: "CDT vaccine dewormer fecal test FAMACHA barber pole worm ivermectin fenbendazole albendazole coccidiosis Corid temperature vitals withdrawal period" },
        { url: "/guide/hoof-care-grooming", title: "Hoof Care & Grooming", keywords: "hoof trimming rot scald shears grooming coat brush bathing" },
        { url: "/guide/breeding-kidding", title: "Breeding & Kidding", keywords: "buck doe breeding heat cycle estrus gestation pregnancy kidding birth labor delivery kids due date" },
        { url: "/guide/bottle-feeding-kid-care", title: "Bottle Feeding & Kid Care", keywords: "bottle baby kid colostrum milk replacer schedule disbudding castration banding tattooing weaning" },
        { url: "/guide/security-predator-proofing", title: "Security & Predator Proofing", keywords: "predator coyote dog fox bear guardian livestock guard dog LGD electric fence security camera night pen" },
        { url: "/guide/behavior-training-enrichment", title: "Behavior & Enrichment", keywords: "behavior training enrichment toys climbing headbutting dominance hierarchy boredom escape aggression" },
        { url: "/guide/seasonal-care", title: "Seasonal Care", keywords: "winter summer spring fall heat cold frostbite water heater fans shade coat" },
        { url: "/guide/checklists", title: "Checklists", keywords: "daily weekly monthly annual checklist routine tasks feeding watering cleaning inspection" },
        { url: "/guide/recordkeeping-forms", title: "Record Keeping & Forms", keywords: "records forms log health breeding kidding weight medication expenses printable" },
        { url: "/guide/common-problems-triage", title: "Common Problems & Triage", keywords: "bloat scours diarrhea limping abscess CL soremouth pinkeye pneumonia listeriosis polio enterotoxemia emergency first aid triage" },
        { url: "/guide/glossary-resources", title: "Glossary & Resources", keywords: "glossary terms definitions rumen browse wether doe buck kid yearling resources books websites" },
        { url: "/guide/calculators", title: "Calculators", keywords: "calculator dose weight medication gestation due date feed cost" },
        { url: "/guide/barn-pack", title: "Barn Pack", keywords: "barn pack emergency kit supplies first aid thermometer syringe electrolytes" },
        { url: "/guide/milking-dairy", title: "Milking & Dairy", keywords: "milking milk stand pail dairy pasteurization chilling mastitis CMT drying off freshen udder teat" },
        { url: "/guide/meat-goats", title: "Meat Goats", keywords: "meat Boer Kiko Spanish Savanna market weight processing butcher USDA finishing feed conversion" },
        { url: "/guide/fiber-goats", title: "Fiber Goats", keywords: "fiber Angora mohair cashmere Pygora Nigora shearing fleece spinning roving micron" },
        { url: "/guide/legal-zoning", title: "Legal & Zoning", keywords: "legal zoning permit HOA ordinance livestock law regulation transport health certificate scrapie raw milk liability insurance" },
        { url: "/guide/poisonous-plants", title: "Poisonous Plants", keywords: "poisonous toxic plants azalea rhododendron yew cherry nightshade hemlock oleander oak acorn fern safe plants" },
        { url: "/guide/goat-milk-recipes", title: "Goat Milk Recipes", keywords: "recipe cheese chevre feta yogurt soap lotion cajeta ice cream milk cooking" },
        { url: "/guide/symptom-checker", title: "Symptom Checker", keywords: "symptom checker diagnosis sick goat lethargic bloated limping diarrhea fever cough not eating" }
    ];

    const input = document.getElementById('search-input');
    const resultsDiv = document.getElementById('search-results');
    const statusEl = document.getElementById('search-status');
    if (!input || !resultsDiv) return;

    let debounceTimer;

    input.addEventListener('input', function () {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => doSearch(this.value.trim()), 200);
    });

    // Support ?q= query param
    const params = new URLSearchParams(window.location.search);
    const q = params.get('q');
    if (q) {
        input.value = q;
        doSearch(q);
    }

    function doSearch(query) {
        if (!query) {
            resultsDiv.innerHTML = '';
            statusEl.textContent = '';
            return;
        }

        const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
        const scored = PAGES.map(page => {
            const haystack = (page.title + ' ' + page.keywords).toLowerCase();
            let score = 0;
            let matchedTerms = 0;
            for (const term of terms) {
                if (haystack.includes(term)) {
                    matchedTerms++;
                    // title match worth more
                    if (page.title.toLowerCase().includes(term)) score += 10;
                    // keyword match
                    const re = new RegExp(term, 'gi');
                    const matches = haystack.match(re);
                    if (matches) score += matches.length;
                }
            }
            // bonus for matching ALL terms
            if (matchedTerms === terms.length) score += 20;
            return { ...page, score, matchedTerms };
        })
        .filter(r => r.score > 0)
        .sort((a, b) => b.score - a.score);

        statusEl.textContent = scored.length
            ? `Found ${scored.length} result${scored.length !== 1 ? 's' : ''} for "${query}"`
            : `No results found for "${query}"`;

        if (scored.length === 0) {
            resultsDiv.innerHTML = `
                <div class="bg-slate-50 p-6 rounded-lg text-center">
                    <p class="text-slate-600">No pages matched your search. Try different keywords.</p>
                    <p class="text-sm text-slate-500 mt-2">Example searches: "bloat", "Nigerian Dwarf", "hoof trimming", "copper bolus"</p>
                </div>`;
            return;
        }

        resultsDiv.innerHTML = scored.map(r => {
            // Highlight matched terms in keywords for context snippet
            let snippet = r.keywords;
            for (const term of terms) {
                const re = new RegExp('(' + term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'gi');
                snippet = snippet.replace(re, '<mark class="bg-emerald-100 text-emerald-800 rounded px-0.5">$1</mark>');
            }
            return `
                <a href="${r.url}" class="block bg-white p-5 rounded-lg shadow-md border border-slate-200 hover:border-emerald-300 hover:shadow-lg transition-all group">
                    <h3 class="text-lg font-bold text-slate-900 group-hover:text-emerald-600 transition-colors">${r.title}</h3>
                    <p class="text-sm text-slate-500 mt-1">${r.url}</p>
                    <p class="text-sm text-slate-600 mt-2">Related: ${snippet}</p>
                </a>`;
        }).join('');
    }
})();
