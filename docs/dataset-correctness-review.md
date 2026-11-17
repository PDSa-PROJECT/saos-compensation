# Przegląd poprawności danych i proste propozycje napraw

Data przeglądu: 17 listopada 2026 r.

## Zakres

Przegląd obejmuje zapisane `record.json`, `award.json`, `source.txt` i `model_calls.json` dla 17 ukończonych przypadków z `tmp/test/`. Nie obejmuje niedokończonego przypadku `259002` ani odrzuconych spraw, dla których nie zachowano artefaktów. Jest to ocena zapisanych danych, a nie niezależny pomiar jakości ekstraktora na reprezentatywnym zbiorze.

W próbie znajduje się 16 rekordów z `valid=true` oraz jeden rekord debugowy z `valid=false`. Dziewięć zaakceptowanych rekordów ma błędny target. Trzy kolejne wymagają poprawienia cech lub wcześniejszej wypłaty. Rekord debugowy nie zawiera kwoty dostępnej w sentencji. W pozostałych czterech przypadkach nie stwierdzono podstawowego błędu targetu ani obowiązkowego opisu szkody w sprawdzonym zakresie.

Oczekiwany target oznacza sumę jednorazowych świadczeń głównych objętych modelowaną sprawą. Nie obejmuje odsetek, kosztów procesu ani wcześniejszych wypłat. Kwoty utrzymane w mocy podane w historycznych opisach apelacji służą wyjaśnieniu starych błędów. Dla wdrożenia wybrano target z bieżącego rozstrzygnięcia: apelacje jedynie utrzymujące wcześniejsze świadczenia i zasądzające koszty są odrzucane.

Poniższe opisy i adnotacje były podstawą zmian. Wyniki wdrożenia i jego ograniczenia podano w końcowej sekcji dokumentu. Nie wymagają nowego modelu, rozbudowanej analizy prawnej ani przebudowy pipeline'u. Mają ograniczyć widoczne błędy, również kosztem pozostawienia niektórych kwot jako nieustalonych.

## Zasady proponowanych zmian

1. Najpierw analizować sentencję, a dopiero przy braku jednoznacznego wyniku wybrane fragmenty uzasadnienia. Samo większe cosine similarity w dalszej części dokumentu nie powinno wypierać jednoznacznej kwoty z sentencji.
2. Przed wyborem świadczenia głównego odfiltrować żądania stron, koszty procesu, wcześniejsze wypłaty i historyczne rozstrzygnięcia. Odsetki od świadczenia głównego oddzielać od kwoty, zamiast odrzucać całą klauzulę.
3. Dla denial wymagać wyraźnego sformułowania oddalenia lub odmowy. Odfiltrować zwroty o oddaleniu części żądania i apelacji. Podobieństwo semantyczne nie jest samo w sobie dowodem pełnego oddalenia powództwa.
4. Rozszerzać wzorce o konkretne brakujące konstrukcje, np. świadczenie główne z odsetkami, dalszą kwotę po wcześniejszej wypłacie i wyraźne rozdzielenie kosztów procesu. Nie dodawać kolejnych ogólnych zdań tylko po to, żeby zwiększyć liczbę wzorców.
5. Dla wcześniejszej wypłaty najpierw wyodrębnić liczby z walutą, a Basala pytać o rolę znalezionej kwoty. Obecne pytanie już wymaga samej kwoty z walutą, ale model często zwraca długi lub nieprawidłowy fragment. Samo powtórzenie tej instrukcji może nie wystarczyć.
6. Odrzucać z cech same markery dowodowe i wymagać zgodności opisu z osobą, której dotyczy target. Doprecyzowanie pytania o nazwę lub inicjały właściwej osoby jest prostszym pierwszym krokiem niż budowa osobnego mechanizmu identyfikacji wszystkich uczestników.
7. Zmiany progów sprawdzać pojedynczo. Nie obniżać globalnie progów Basala w celu odzyskania wcześniejszych wypłat: mogłoby to jednocześnie przepuścić więcej kosztów i nieistotnych opisów. Najpierw poprawić filtr i format odpowiedzi.

**podstawowy fix**
najpierw szukamy grup innych niz nasz target
- case denial potwierdzony - sprawe oddalono
- inne przypadki: podnosimy prog confidence 0.7 -> 0.85
- zdania z kwotami dzielimy na części, tak zeby zlapac otoczenie tam gdzie występuje kwota (5 słów przed i 5 po kwocie)
- badamy podobienstwo tego wycinka, nie calego zdania do konkretnych klas i klasyfikujemy te wycinki
- wycinki mogą się zazębiać
- jeśli dany wycinek (otoczenie kwoty) został przyporządkowany do konkretnej grupy, nie sprawdzamy go juz do targetu

- nalezy zadać basalowi dokladniejsze pytania, ktore pozwolą rozroznic

## Niepoprawne lub niepełne przypadki

### 256976 — I C 1092/15

**Opis:** zapisano `total=35000`, a sentencja zasądza **30 000 zł**. `prior_payment=0`, mimo potwierdzonej wcześniejszej wypłaty **5000 zł**.

**Przyczyna:** jako target wybrano rozważania o odpowiedniej łącznej wysokości zadośćuczynienia przed odjęciem wcześniejszej wypłaty. Prawidłową klauzulę z sentencji zakwalifikowano jako odsetki. Basal zwrócił dla wcześniejszej wypłaty zbyt szeroki fragment o niskiej pewności.

**Proponowane rozwiązanie:** podstawowy fix

### 256991 — I C 1227/15

**Opis:** zapisano `total=4000` i jedną osobę. Sentencja zasądza **7850 zł = 4850 + 2000 + 1000** dla **trzech beneficjentek**. W źródle potwierdzono także wcześniejszą wypłatę **1000 zł**. Cechy opisują tylko jedną z beneficjentek.

**Przyczyna:** wybrano teoretyczną kwotę zadośćuczynienia jednej osoby z uzasadnienia. Nie zsumowano odrębnych punktów sentencji ani nie uwzględniono wszystkich odbiorczyń. Do jednego targetu przypisano zbyt wąski opis szkody.

**Proponowane rozwiązanie:** suma jest ok. liczba beneficjentek się nie zgadza. czy odpowiada na to basal? jeśli tak to trzeba zadać mu dokładniejsze pytanie. jeśli nie, liczba beneficjentów do usunięcia (lepiej nie usuwajmy)

### 257024 — I C 1710/14

**Opis:** zapisano `total=2400`, chociaż zasądzono **20 500 zł**. `damage` zawiera tylko „Bezsporne.”. Wcześniejsza wypłata **4500 zł** została zapisana jako zero. Rekord ma `valid=true`.

**Przyczyna:** do targetu trafiło wynagrodzenie prawnika opisane przy rozliczaniu kosztów. Słowa w wybranym prefiksie nie dopuściły odpowiedniej kategorii wykluczającej. Basal uznał marker dowodowy za opis szkody z trafnością około 0,670.

**Proponowane rozwiązanie:** fix podstawowy + rozszerz baze słów/ zdań + wyzsze progi (chyba juz są)

### 260046 — I ACa 504/16

**Opis:** zapisano **5400 zł kosztów apelacji** jako target. Utrzymane świadczenia główne wynoszą **104 053 zł = 100 000 + 4053**.

**Przyczyna:** zdanie zawierające „tytułem zwrotu kosztów procesu w instancji odwoławczej” wygrało jako `judgment`, mimo dopuszczenia kategorii kosztowej. Sam wynik similarity nie zapewnił poprawnej kategorii.

**Proponowane rozwiązanie:** fix podstawowy


### 260063 — I C 172/15

**Opis:** zapisano `total=not_available`, `valid=false`, mimo że sentencja zasądza **14 000 zł**.

**Przyczyna:** wybrano zdanie o rozszerzeniu żądania z 6000 zł o kolejne 8000 zł. Parser prawidłowo odmówił uznania takiego zdania z dwiema kwotami za jednoznaczny target. Błąd wystąpił wcześniej, przy filtracji kandydatów.

**Proponowane rozwiązanie:** Poszerzyć wzorce `request` o te konstrukcje. Najpierw sprawdzić prostą kwotę 14 000 zł w sentencji. Zachować odrzucenie fragmentu z dwiema kwotami — nie naprawiać tego przez zgadywanie, którą wybrać.
zgadza sie
### 260384 — I ACa 662/16

**Opis:** zapisano `total=35000`. Utrzymane świadczenie wynosi **36 800 zł = 32 000 zł zadośćuczynienia + 4800 zł odszkodowania**. W źródle jest potwierdzona wcześniejsza wypłata zadośćuczynienia **3000 zł**, a w rekordzie `prior_payment=0`.

**Przyczyna:** wybrano zdanie o adekwatnej wysokości krzywdy przed uwzględnieniem wcześniejszej wypłaty. Nie wybrano opisu kwoty rzeczywiście zasądzonej. Fragment o wcześniejszej wypłacie nie przeszedł ekstrakcji Basala.

**Proponowane rozwiązanie:** obniżyć priorytet opisów „adekwatną kwotą będzie” i „odpowiednie zadośćuczynienie wynosi”. Preferować konstrukcje „zasądził”, „zasądzając” i „należało zasądzić”, z kwotą i odbiorcą. W tym źródle istnieje jawne podsumowanie 36 800 zł, więc nie trzeba budować rozbudowanego rozliczenia. Jeśli podsumowania nie da się bezpiecznie wskazać, odrzucić przypadek. Wcześniejszą wypłatę wyodrębnić jako liczbę z walutą.
niech tak będzie. jednak musimy pozostawić konkstrukcje zdaniowe. podstawowy fix powinien zaradzić

### 275542 — II Ca 362/16

**Opis:** kwota **5000 zł** odpowiada powodowi **D. Ł. (1)** objętemu apelacją, ale `damage` opisuje jego córkę **D. Ł. (2)**. Wcześniejsze zadośćuczynienie dla powoda wynosiło **15 000 zł**, a zapisano zero.

**Przyczyna:** w uzasadnieniu opisano kilka osób z tej samej rodziny. Pytanie o poszkodowanego nie ograniczyło odpowiedzi do właściwego uczestnika. Wystarczyło semantycznie poprawne zdanie o szkodzie, nawet jeśli dotyczyło innej osoby.

**Proponowane rozwiązanie:** pytania do basala powinny być ogólne (pasowac do kazdego case'a), ale nie pozostawiać mu takiego pola do interpretacji. dobre pytanie powinno ograniczac takie wątpliwości basala. innych pytan tez to sie tyczy

### 275708 — V ACa 154/16

**Opis:** target **41 000 zł** jest poprawny. Błędna jest informacja o wcześniejszej wypłacie: zapisano zero zamiast potwierdzonych **9000 zł**.

**Przyczyna:** trafny kontekst wypłaty został znaleziony, ale Basal zwrócił „wypłacił kwotę 9.000” bez waluty i z pewnością około 0,115. Niespełnienie warunków ekstrakcji zamieniono na zero.

**Proponowane rozwiązanie:** „wypłacił kwotę 9.000” - filtrować samą liczbe. NIGDY nie potrzebujemy waluty. zakladamy ze to zł (wyszukiwanie powinno zostać tu niezmienne), mam na mysli samą filtracje przed zapisaniem.
### 289025 — I C 817/14

**Opis:** target **40 000 zł** jest liczbowo poprawny, ale `damage` to „Dowód: przesłuchanie powódki K. Z. (1)”. Źródło opisuje **przetokę tchawiczo-przełykową**, dodatkową operację i dolegliwości.

**Przyczyna:** marker dowodowy uzyskał trafność dla szkody około 0,742. Target wybrano z nagłówka żądania, a nie z rozstrzygnięcia; w tej sprawie obie kwoty są takie same, co maskuje błąd metody.

**Proponowane rozwiązanie:** podstawowy fix + wyzszy prog

### 304803 — I C 768/15

**Opis:** zapisano **8000 zł** z wcześniejszego postępowania karnego. Bieżący wyrok zasądza **94 146,99 zł na rzecz ubezpieczyciela w sprawie regresowej**. Cechy opisują obrażenia poszkodowanego G. R., a nie szkodę bieżącego beneficjenta świadczenia.

**Przyczyna:** ogólny filtr słów dopuścił historyczną nawiązkę jako target. Samo wystąpienie zadośćuczynienia w tekście wystarczyło do zakwalifikowania całej sprawy jako odpowiedniego przykładu.

**Proponowane rozwiązanie:** brakuje informacji o tym jaki dokladnie fragment tekstu oznaczono jako target. wyzszy próg + biezący fix na ten moment. jak skonczysz kodować przedstaw wiecej szczegółów tego/ biezącego rekordu

### 333609 — I C 140/15

**Opis:** zapisano `total=0`, jedną osobę i `prior_payment=0`. Sentencja zasądza **445 000 zł = 170 000 + 170 000 + 45 000 + 30 000 + 30 000** dla **pięciu beneficjentów**. Opisane wcześniejsze świadczenia główne wynoszą łącznie **195 000 zł**. `damage` opisuje tylko korzystne rokowania części powodów.

**Przyczyna:** jako denial wybrano zdanie, w którym sąd mówi o zasądzeniu 110 000 zł. Podobieństwo 0,865 przekroczyło próg 0,85, chociaż zdanie nie stwierdza oddalenia. Ścieżka zera ominęła dalsze rozpoznanie kwot.

**Proponowane rozwiązanie:** rozszerzyć baze denial. podać dokładne zdania które źle oznaczono po zakonczeniu kodowania.

### 337201 — I C 66/15

**Opis:** zapisano `total=0` i `prior_payment=0`. Sentencja zasądza **150 000 zł**; wcześniejsza wypłata wynosi **110 000 zł**.

**Przyczyna:** zdanie o braku podstaw do przyznania pełnej żądanej kwoty potraktowano jako całkowite oddalenie. Similarity wyniosło 0,886. Uzasadnienie obniżenia żądania nie jest dowodem braku jakiegokolwiek świadczenia.

**Proponowane rozwiązanie:** rozszerzyć wzorce. podstawowy fix z podziałem zdań na wycinki powinien zrobić robotę.

### 369009 — I C 537/16

**Opis:** zapisano `total=30000`. Sentencja zasądza **170 000 zł = 30 000 zł odszkodowania + 140 000 zł zadośćuczynienia**. Wcześniejsze świadczenia uwzględnione przy zadośćuczynieniu to **60 000 zł = 40 000 + 20 000**, a zapisano zero.

**Przyczyna:** wybrano tylko jeden składnik. Drugą klauzulę skierowano do odsetek, ponieważ obok kwoty głównej wymieniała również kwoty stanowiące podstawę naliczania odsetek.

**Proponowane rozwiązanie:** wycinki do poszczególnych kwot powinny zrobić robotę. w ten sposób jedna kwota moze isc do targetu, kolejna do prior payment

## Przypadki bez stwierdzonego podstawowego błędu

| Case | Potwierdzony target | Ocena w sprawdzonym zakresie |
|---|---:|---|
| 257916 | 0 zł | Rzeczywiste oddalenie powództwa; opis szkody ma podstawę w źródle. |
| 258067 | 0 zł | Rzeczywiste oddalenie powództwa; opis szkody dotyczy właściwej powódki. |
| 258134 | 10 000 zł | Świadczenie na rzecz pokrzywdzonej zgodne z sentencją. |
| 274172 | 4000 zł | Nawiązka na rzecz pokrzywdzonego zgodna z sentencją. |

Nie oznacza to pełnego potwierdzenia jakości wszystkich cech. Brak opcjonalnego `cause` lub `limitations` nie jest sam w sobie dowodem błędu rekordu.

## Problemy wspólne i kolejność sprawdzania poprawek

Wszystkie 17 rekordów nie zawiera nowego `court_type`. Zapisana konfiguracja trwającego przebiegu również go nie wybierała. To różnica konfiguracji danych, a nie błąd rozpoznawania sądu. Najprostsze postępowanie to nowy katalog wyjściowy z aktualną konfiguracją, bez nadpisywania wcześniejszych artefaktów.

Wszystkie zapisane `prior_payment` wynoszą zero. W części spraw oznacza to brak potwierdzenia ekstrakcji, mimo dodatniej wypłaty w źródle. Taki fallback jest dopuszczony przez obecny kontrakt programu, ale nie może być interpretowany jako pewna informacja, że nic wcześniej nie zapłacono.

Zalecana kolejność małych zmian:

1. Odfiltrować same markery dowodowe z `damage` oraz jednoznaczne koszty procesu z targetu.
2. Zmienić kolejność: sentencja przed uzasadnieniem, żądania i koszty przed wyborem `judgment`.
3. Dodać słowne wykluczenia dla częściowego oddalenia i zwykłych zdań o zasądzeniu błędnie wybranych jako denial.
4. Oddzielić główną kwotę świadczenia od odsetek; sprawdzić sumowanie prostych punktów sentencji.
5. Doprecyzować osobę w pytaniach do Basala i zastąpić swobodne wydobywanie wypłaty wyborem spośród kwot znalezionych w tekście.
6. Uzupełnić tylko brakujące konstrukcje wzorców. Dopiero potem porównywać progi na oznaczonych przykładach.

Po każdej zmianie sprawdzić zarówno wskazane błędne przypadki, jak i cztery przypadki z poprawnym podstawowym wynikiem. Poprawa jednego przykładu nie wystarcza, jeżeli filtr psuje wcześniej prawidłowe odczyty. Najpierw należy upewnić się, że błędne rekordy nie przechodzą jako poprawne; odzyskanie wszystkich trudniejszych przypadków może pozostać osobnym etapem.

Podczas przeglądu zapisane fragmenty i offsety odpowiadały źródłom. Widoczne problemy dotyczą przede wszystkim znaczenia i roli fragmentu, a nie uszkodzenia plików JSON. Nie wykonywano ponownej ekstrakcji, napraw danych ani niezależnej weryfikacji wszystkich metadanych lokalizacyjnych.

## Wdrożenie i replay po poprawkach — 17 listopada 2026 r.

Zmiany są na branchu `fix/extraction-amount-contexts`, utworzonym z `split-download-processing`. Reguły wykonawcze nie zawierają ID spraw, konkretnych kwot ani nazw osób z powyższych przykładów. Próbka służy do sprawdzania regresji, a nie do wybierania wyjątków w kodzie.

Wdrożono:

- niezależne, mogące się zazębiać wycinki obejmujące kwotę i pięć słów z każdej strony; zachowane są też pełne klauzule i dokładne offsety;
- cosine **ściśle ponad 0.85** oraz ocenę klas innych niż target przed obliczeniem similarity do `judgment` dla pozostałych wycinków;
- wykluczanie jawnych kosztów i podstaw odsetkowych, zachowanie świadczenia głównego z odsetkami oraz preferencję bieżącej sentencji;
- sumowanie odrębnych, potwierdzonych kwot głównych z sentencji, bez duplikatów, i odrzucanie niepełnych lub sprzecznie sklasyfikowanych sum;
- jawne pełne oddalenie jako warunek denial, blokadę oddalenia częściowego, apelacji i żądań stron oraz wybór najlepszego wyniku w całym dopuszczonym zakresie tekstu;
- odrzucanie apelacji jedynie utrzymujących wcześniejsze świadczenia i zasądzających koszty, również w debug; apelacje z nowym zasądzeniem pozostają dopuszczalne;
- liczenie beneficjentów z pełnych klauzul, z zachowaniem numerów przy inicjałach, i przekazanie ich tożsamości do pytań o cechy;
- odrzucanie samych markerów dowodowych oraz dokładniejsze pytania o własną szkodę aktualnych beneficjentów; przy nieustalonym targecie debug nadal wykonuje podstawową ekstrakcję cech;
- potwierdzanie przez Basala roli konkretnej kwoty wcześniejszej wypłaty zamiast swobodnego wydobywania liczby i waluty; PLN jest wymagany w źródle, a zapisywana cecha pozostaje liczbą;
- odrzucanie jawnej dopłaty lub składnika jako niepotwierdzonej sumy wcześniejszych wypłat, bez obniżania progu Basala;
- obsługę zapisu `4. 000 zł` oraz waluty w słownym rozwinięciu, np. `40.000 (czterdzieści tysięcy złotych)`;
- `court_type` bezpośrednio z `division.court.type`, wybór w konfiguracji i kodowanie kategorialne; `instance` pozostaje niezależną cechą.

Liczby i inicjały są neutralizowane wyłącznie na potrzeby embeddingu. Źródłowy wycinek, jego kwota i wskazanie beneficjentów nie są w ten sposób zmieniane. Numer wersji ekstraktora pozostał bez zmian. Zmienione pytania, wzorce, progi i wybór cech wymagają nowego katalogu przetwarzania; starych danych nie nadpisano.

### Wyniki targetów

Replay wykonał rzeczywisty, zapisany MiniLM na CPU na wszystkich 17 tekstach. Poniższa tabela dotyczy wyboru i parsowania targetu oraz jawnych beneficjentów, **nie nowej pełnej ekstrakcji cech ani ponownego zatwierdzenia `valid`**.

| Case | Target po replayu | Uwaga |
|---|---:|---|
| 256976 | 30000 zł |  |
| 256991 | 7850 zł | Jawni beneficjenci: 3. |
| 257024 | 20500 zł |  |
| 257916 | 0 zł | Zachowany poprawny target kontrolny. |
| 258067 | 0 zł | Zachowany poprawny target kontrolny. |
| 258134 | 10000 zł | Zachowany poprawny target kontrolny. |
| 260046 | odrzucony | Apelacja bez nowego zasądzenia głównego. |
| 260063 | 14000 zł |  |
| 260384 | odrzucony | Apelacja bez nowego zasądzenia głównego. |
| 274172 | 4000 zł | Zachowany poprawny target kontrolny. |
| 275542 | odrzucony | Apelacja bez nowego zasądzenia głównego. |
| 275708 | odrzucony | Apelacja bez nowego zasądzenia głównego. |
| 289025 | 40000 zł |  |
| 304803 | nieustalony | Brak zaakceptowanego targetu; stare 8000 zł nie jest przyjmowane. |
| 333609 | 445000 zł | Jawni beneficjenci: 5. |
| 337201 | 150000 zł |  |
| 369009 | 170000.00 zł |  |

Wynik: **12 targetów zgodnych z opisanymi wartościami bieżących rozstrzygnięć, 4 odrzucone apelacje, 1 target nieustalony**. Wszystkie cztery przypadki kontrolne zachowały poprawne kwoty. Nie jest to estymata trafności na niezależnym zbiorze.

### Wcześniejsze wypłaty i ograniczenia

Finalne pytanie sprawdzono na rzeczywistym, lokalnym `Remek/basal-2.0-4.5B` na CPU. Bez zmiany `amount_minimum_probability=0.6` potwierdzono:

| Case | Kwota | Ocena roli |
|---|---:|---:|
| 256976 | 5000 zł | 0.848 |
| 257024 | 4500 zł | 0.851 |
| 337201 | 110000 zł | 0.806 |

Dodatkowe kontrole ról w trakcie prac potwierdziły wypłatę 9000 zł (0.931) i odrzuciły bieżące zasądzenie 150000 zł (0.137) oraz koszty procesu 2417 zł (0.113) jako wcześniejsze wypłaty. Te kontrole nie oznaczają ponownego przyjęcia odrzuconej apelacji 275708.

Nie rozwiązano ogólnego sumowania wielu historycznych wypłat dla kilku osób ani pewnej deduplikacji takich wzmianek. W szczególności odzyskanie 195000 zł dla 333609 oraz pełnych 60000 zł dla 369009 wymaga dalszej weryfikacji. Sam składnik 20000 zł opisany jako wypłacony „ponadto” nie jest zapisywany jako potwierdzona suma. Zero nadal oznacza także brak potwierdzenia ekstrakcji. Nie wykonano pełnej ponownej ekstrakcji wszystkich cech na 17 sprawach; nowe pytania nie są dowodem poprawnego przypisania każdej szkody do osoby.

### Dokładne stare błędne dopasowania

#### 304803

Stary wybrany fragment (`judgment`, cosine 0.757369, offsety `18613:18837`):

> Nie jest uprawnione twierdzenie pozwanego, że zasądzona od pozwanego w postępowaniu karnym na rzecz poszkodowanego G. R. (1) nawiązka w kwocie 8.000zł (egzekwowana przez komornika) wyczerpuje należne pozwanemu odszkodowanie.

Fragment opisuje nawiązkę z wcześniejszej sprawy karnej, a nie bieżące zasądzenie. Powodem w bieżącej sprawie jest ubezpieczyciel (...) S.A., pozwanym Ł. M., a źródło opisuje regres za świadczenia wypłacone G. R. (1). Sentencja zasądza 94146,99 zł. Obrażenia G. R. (1) nie opisują własnej szkody aktualnego beneficjenta. Po poprawkach bieżący kandydat nie przechodzi progu; wynik pozostaje nieustalony. Nie zastępujemy go kwotą z historii postępowania ani zerem. Dalsza ocena tego rodzaju spraw musi również sprawdzić zgodność opisu szkody z beneficjentem.

#### 333609

Stary wybrany fragment (`judgment-denial`, cosine 0.864717, offsety `34998:35130`):

> W związku z powyższym, Sąd zasądził na rzecz powoda pozostałą do zapłaty kwotę 110 000 zł tytułem zadośćuczynienia (punkt 1 wyroku).

Zdanie wprost opisuje zasądzenie, bez pełnego oddalenia lub odmowy. Jest odrzucane jako denial niezależnie od cosine. Bieżący target wynika z pięciu odrębnych świadczeń: 170000 + 170000 + 45000 + 30000 + 30000 = 445000 zł.

#### 337201

Stary wybrany fragment (`judgment-denial`, cosine 0.886387, offsety `31371:31474`):

> Zdaniem Sądu nie było podstaw do ustalenia wysokości zadośćuczynienia w kwocie zażądanej przez powódkę.

Zdanie wyjaśnia nieuwzględnienie całej żądanej wysokości, bez stwierdzenia całkowitego oddalenia powództwa. Nie spełnia warunku jawnego denial. Bieżąca sentencja daje 150000 zł.

### Sprawdzenia ogólne

Pełny zestaw automatyczny: **535 passed, 5 skipped**; Ruff i sprawdzenie białych znaków przeszły. Oprócz przykładów z dokumentu testy obejmują odmienne formy gramatyczne oddalenia, różne kwoty i waluty, akcesoryjne odsetki, koszty procesu i sądowe, leczenie z opinią biegłego oraz odszkodowanie na rzecz Skarbu Państwa. Sama wzmianka o pełnomocniku, biegłym lub publicznej stronie nie stanowi wystarczającej reguły kosztowej. Testy sprawdzają także niepełne sumy, różne osoby, nakładające się wycinki, apelacje ze zmianą świadczenia i niezależne źródło typu sądu.
