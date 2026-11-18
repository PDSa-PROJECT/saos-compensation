# Przegląd poprawności danych i proste propozycje napraw

Data przeglądu: 17 listopada 2026 r.

## Zakres

Przegląd obejmuje zapisane `record.json`, `award.json`, `source.txt` i `model_calls.json` dla 17 ukończonych przypadków z `tmp/test/`. Nie obejmuje niedokończonego przypadku `259002` ani odrzuconych spraw, dla których nie zachowano artefaktów. Jest to ocena zapisanych danych, a nie niezależny pomiar jakości ekstraktora na reprezentatywnym zbiorze.

W próbie znajduje się 16 rekordów z `valid=true` oraz jeden rekord debugowy z `valid=false`. Dziewięć zaakceptowanych rekordów ma błędny target. Trzy kolejne wymagają poprawienia cech lub wcześniejszej wypłaty. Rekord debugowy nie zawiera kwoty dostępnej w sentencji. W pozostałych czterech przypadkach nie stwierdzono podstawowego błędu targetu ani obowiązkowego opisu szkody w sprawdzonym zakresie.

Oczekiwany target oznacza sumę jednorazowych świadczeń głównych objętych modelowaną sprawą. Nie obejmuje odsetek, kosztów procesu ani wcześniejszych wypłat. Dla opisanych apelacji podano świadczenie utrzymane w mocy. Jeżeli dataset ma obejmować wyłącznie nowe zasądzenia w bieżącym wyroku, prostszą alternatywą jest odrzucenie takich apelacji.

Poniższe rozwiązania są propozycjami. Nie zostały w ramach tego dokumentu wdrożone ani sprawdzone eksperymentalnie. Nie wymagają nowego modelu, rozbudowanej analizy prawnej ani przebudowy pipeline'u. Mają ograniczyć widoczne błędy, również kosztem pozostawienia niektórych kwot jako nieustalonych.

## Zasady proponowanych zmian

1. Najpierw analizować sentencję, a dopiero przy braku jednoznacznego wyniku wybrane fragmenty uzasadnienia. Samo większe cosine similarity w dalszej części dokumentu nie powinno wypierać jednoznacznej kwoty z sentencji.
2. Przed wyborem świadczenia głównego odfiltrować żądania stron, koszty procesu, wcześniejsze wypłaty i historyczne rozstrzygnięcia. Odsetki od świadczenia głównego oddzielać od kwoty, zamiast odrzucać całą klauzulę.
3. Dla denial wymagać wyraźnego sformułowania oddalenia lub odmowy. Odfiltrować zwroty o oddaleniu części żądania i apelacji. Podobieństwo semantyczne nie jest samo w sobie dowodem pełnego oddalenia powództwa.
4. Rozszerzać wzorce o konkretne brakujące konstrukcje, np. świadczenie główne z odsetkami, dalszą kwotę po wcześniejszej wypłacie i wyraźne rozdzielenie kosztów procesu. Nie dodawać kolejnych ogólnych zdań tylko po to, żeby zwiększyć liczbę wzorców.
5. Dla wcześniejszej wypłaty najpierw wyodrębnić liczby z walutą, a Basala pytać o rolę znalezionej kwoty. Obecne pytanie już wymaga samej kwoty z walutą, ale model często zwraca długi lub nieprawidłowy fragment. Samo powtórzenie tej instrukcji może nie wystarczyć.
6. Odrzucać z cech same markery dowodowe i wymagać zgodności opisu z osobą, której dotyczy target. Doprecyzowanie pytania o nazwę lub inicjały właściwej osoby jest prostszym pierwszym krokiem niż budowa osobnego mechanizmu identyfikacji wszystkich uczestników.
7. Zmiany progów sprawdzać pojedynczo. Nie obniżać globalnie progów Basala w celu odzyskania wcześniejszych wypłat: mogłoby to jednocześnie przepuścić więcej kosztów i nieistotnych opisów. Najpierw poprawić filtr i format odpowiedzi.

**podstawowy fix**
najpierw szukamy gru

## Niepoprawne lub niepełne przypadki

### 256976 — I C 1092/15

**Opis:** zapisano `total=35000`, a sentencja zasądza **30 000 zł**. `prior_payment=0`, mimo potwierdzonej wcześniejszej wypłaty **5000 zł**.

**Przyczyna:** jako target wybrano rozważania o odpowiedniej łącznej wysokości zadośćuczynienia przed odjęciem wcześniejszej wypłaty. Prawidłową klauzulę z sentencji zakwalifikowano jako odsetki. Basal zwrócił dla wcześniejszej wypłaty zbyt szeroki fragment o niskiej pewności.

**Proponowane rozwiązanie:** mamy juz w targets.yaml baze do rozpoznawania prior payment.

### 256991 — I C 1227/15

**Opis:** zapisano `total=4000` i jedną osobę. Sentencja zasądza **7850 zł = 4850 + 2000 + 1000** dla **trzech beneficjentek**. W źródle potwierdzono także wcześniejszą wypłatę **1000 zł**. Cechy opisują tylko jedną z beneficjentek.

**Przyczyna:** wybrano teoretyczną kwotę zadośćuczynienia jednej osoby z uzasadnienia. Nie zsumowano odrębnych punktów sentencji ani nie uwzględniono wszystkich odbiorczyń. Do jednego targetu przypisano zbyt wąski opis szkody.

**Proponowane rozwiązanie:** najpierw przejść po punktach sentencji. Odrzucić punkty o kosztach i wyodrębnić kwoty po „zasądza ... na rzecz ...”. W tym prostym przypadku zsumować trzy świadczenia i policzyć ich jawne odbiorczynie. W pytaniu o szkodę wskazać wszystkie trzy osoby. Jeżeli nie uda się zebrać zgodnych cech, nie akceptować samej sumy z opisem jednej osoby.

### 257024 — I C 1710/14

**Opis:** zapisano `total=2400`, chociaż zasądzono **20 500 zł**. `damage` zawiera tylko „Bezsporne.”. Wcześniejsza wypłata **4500 zł** została zapisana jako zero. Rekord ma `valid=true`.

**Przyczyna:** do targetu trafiło wynagrodzenie prawnika opisane przy rozliczaniu kosztów. Słowa w wybranym prefiksie nie dopuściły odpowiedniej kategorii wykluczającej. Basal uznał marker dowodowy za opis szkody z trafnością około 0,670.

**Proponowane rozwiązanie:** przed wyborem kwoty głównej odfiltrować zwroty o wynagrodzeniu prawnika i zwrocie kosztów procesu, z uwzględnieniem wariantów pisowni. Pierwszeństwo dać 20 500 zł z sentencji. Odrzucać samodzielne „Bezsporne.” przed oceną cech przez Basala. W pytaniu o szkodę wymagać zdania opisującego faktyczny uszczerbek, a nie oznaczenia dowodu. Do czasu uzyskania takiego opisu odrzucić rekord, również przy włączonym debug.

### 260046 — I ACa 504/16

**Opis:** zapisano **5400 zł kosztów apelacji** jako target. Utrzymane świadczenia główne wynoszą **104 053 zł = 100 000 + 4053**.

**Przyczyna:** zdanie zawierające „tytułem zwrotu kosztów procesu w instancji odwoławczej” wygrało jako `judgment`, mimo dopuszczenia kategorii kosztowej. Sam wynik similarity nie zapewnił poprawnej kategorii.

**Proponowane rozwiązanie:** zwroty „tytułem zwrotu kosztów procesu” i „kosztów postępowania apelacyjnego” potraktować jako twardy filtr przed wyborem targetu. „Oddala apelację” nie może oznaczać ani zera, ani zasądzenia kosztów jako odszkodowania. Najprostszy bezpieczny wariant to odrzucić tę apelację, jeśli na obecnym etapie nie odczytujemy jednoznacznie utrzymanych świadczeń z opisu zaskarżonego wyroku.

### 260063 — I C 172/15

**Opis:** zapisano `total=not_available`, `valid=false`, mimo że sentencja zasądza **14 000 zł**.

**Przyczyna:** wybrano zdanie o rozszerzeniu żądania z 6000 zł o kolejne 8000 zł. Parser prawidłowo odmówił uznania takiego zdania z dwiema kwotami za jednoznaczny target. Błąd wystąpił wcześniej, przy filtracji kandydatów.

**Proponowane rozwiązanie:** przed kategorią `judgment` odfiltrować sformułowania „powód zmienił żądanie”, „wniósł o zasądzenie” i „rozszerzył żądanie”. Poszerzyć wzorce `request` o te konstrukcje. Najpierw sprawdzić prostą kwotę 14 000 zł w sentencji. Zachować odrzucenie fragmentu z dwiema kwotami — nie naprawiać tego przez zgadywanie, którą wybrać.

### 260384 — I ACa 662/16

**Opis:** zapisano `total=35000`. Utrzymane świadczenie wynosi **36 800 zł = 32 000 zł zadośćuczynienia + 4800 zł odszkodowania**. W źródle jest potwierdzona wcześniejsza wypłata zadośćuczynienia **3000 zł**, a w rekordzie `prior_payment=0`.

**Przyczyna:** wybrano zdanie o adekwatnej wysokości krzywdy przed uwzględnieniem wcześniejszej wypłaty. Nie wybrano opisu kwoty rzeczywiście zasądzonej. Fragment o wcześniejszej wypłacie nie przeszedł ekstrakcji Basala.

**Proponowane rozwiązanie:** obniżyć priorytet opisów „adekwatną kwotą będzie” i „odpowiednie zadośćuczynienie wynosi”. Preferować konstrukcje „zasądził”, „zasądzając” i „należało zasądzić”, z kwotą i odbiorcą. W tym źródle istnieje jawne podsumowanie 36 800 zł, więc nie trzeba budować rozbudowanego rozliczenia. Jeśli podsumowania nie da się bezpiecznie wskazać, odrzucić przypadek. Wcześniejszą wypłatę wyodrębnić jako liczbę z walutą.

### 275542 — II Ca 362/16

**Opis:** kwota **5000 zł** odpowiada powodowi **D. Ł. (1)** objętemu apelacją, ale `damage` opisuje jego córkę **D. Ł. (2)**. Wcześniejsze zadośćuczynienie dla powoda wynosiło **15 000 zł**, a zapisano zero.

**Przyczyna:** w uzasadnieniu opisano kilka osób z tej samej rodziny. Pytanie o poszkodowanego nie ograniczyło odpowiedzi do właściwego uczestnika. Wystarczyło semantycznie poprawne zdanie o szkodzie, nawet jeśli dotyczyło innej osoby.

**Proponowane rozwiązanie:** w pytaniu do Basala wskazać dokładnie „powód D. Ł. (1), mąż zmarłej”. Przed dopuszczeniem opisu odfiltrować fragmenty jawnie dotyczące D. Ł. (2). Nie sumować wszystkich kwot z rodzinnej sprawy pierwszoinstancyjnej, bo zakres tej apelacji jest węższy. Gdy model nie odróżni osób, pozostawić opis jako nieustalony zamiast przypisywać szkodę córki ojcu.

### 275708 — V ACa 154/16

**Opis:** target **41 000 zł** jest poprawny. Błędna jest informacja o wcześniejszej wypłacie: zapisano zero zamiast potwierdzonych **9000 zł**.

**Przyczyna:** trafny kontekst wypłaty został znaleziony, ale Basal zwrócił „wypłacił kwotę 9.000” bez waluty i z pewnością około 0,115. Niespełnienie warunków ekstrakcji zamieniono na zero.

**Proponowane rozwiązanie:** w znalezionym zdaniu najpierw wyodrębnić pojedynczą kwotę `9000 zł`. Basala pytać krótko, czy jest to wcześniejsze świadczenie wypłacone powódce, zamiast prosić o dowolny fragment tekstu. Na początku nie obniżać globalnie progu 0,6. Rozdzielić w istniejącej diagnostyce brak potwierdzenia od rzeczywistego braku wypłaty.

### 289025 — I C 817/14

**Opis:** target **40 000 zł** jest liczbowo poprawny, ale `damage` to „Dowód: przesłuchanie powódki K. Z. (1)”. Źródło opisuje **przetokę tchawiczo-przełykową**, dodatkową operację i dolegliwości.

**Przyczyna:** marker dowodowy uzyskał trafność dla szkody około 0,742. Target wybrano z nagłówka żądania, a nie z rozstrzygnięcia; w tej sprawie obie kwoty są takie same, co maskuje błąd metody.

**Proponowane rozwiązanie:** przed oceną cech odfiltrować same linie zaczynające się od „Dowód:”, „dowody:” lub zawierające wyłącznie wskazanie dokumentu czy przesłuchania. Skrócić pytanie do Basala do żądania konkretnego opisu uszczerbku danej powódki. Nagłówek „o zadośćuczynienie ...” kierować do żądania lub pomijać; target wybierać najpierw z sentencji. Bez prawidłowego opisu szkody nie akceptować rekordu.

### 304803 — I C 768/15

**Opis:** zapisano **8000 zł** z wcześniejszego postępowania karnego. Bieżący wyrok zasądza **94 146,99 zł na rzecz ubezpieczyciela w sprawie regresowej**. Cechy opisują obrażenia poszkodowanego G. R., a nie szkodę bieżącego beneficjenta świadczenia.

**Przyczyna:** ogólny filtr słów dopuścił historyczną nawiązkę jako target. Samo wystąpienie zadośćuczynienia w tekście wystarczyło do zakwalifikowania całej sprawy jako odpowiedniego przykładu.

**Proponowane rozwiązanie:** dodać wstępny filtr konstrukcji „roszczenie regresowe” i „zwrot wypłaconego odszkodowania”, sprawdzając również, kto jest powodem. Jeśli regres nie jest obecnie modelowany, odrzucić taki przypadek. Nie odrzucać automatycznie każdej sprawy z ubezpieczycielem — istotna jest jego rola jako powoda żądającego zwrotu. Przed wyborem targetu odfiltrować kwoty opisane jako zasądzone we wcześniejszym postępowaniu.

### 333609 — I C 140/15

**Opis:** zapisano `total=0`, jedną osobę i `prior_payment=0`. Sentencja zasądza **445 000 zł = 170 000 + 170 000 + 45 000 + 30 000 + 30 000** dla **pięciu beneficjentów**. Opisane wcześniejsze świadczenia główne wynoszą łącznie **195 000 zł**. `damage` opisuje tylko korzystne rokowania części powodów.

**Przyczyna:** jako denial wybrano zdanie, w którym sąd mówi o zasądzeniu 110 000 zł. Podobieństwo 0,865 przekroczyło próg 0,85, chociaż zdanie nie stwierdza oddalenia. Ścieżka zera ominęła dalsze rozpoznanie kwot.

**Proponowane rozwiązanie:** przed uznaniem denial wymagać wyraźnego zwrotu o oddaleniu lub odmowie i odrzucać jako denial zdania mówiące wyłącznie „sąd zasądził”. Samo ponowne podniesienie progu nie usuwa przyczyny. Następnie zebrać kwoty główne z pierwszych pięciu punktów sentencji, a pominąć punkty o kosztach. W pytaniu o szkodę wymagać opisu straty, nie tylko rokowania na przyszłość. Jeśli nie uda się zebrać zgodnego opisu dla całej grupy, nie akceptować rekordu.

### 337201 — I C 66/15

**Opis:** zapisano `total=0` i `prior_payment=0`. Sentencja zasądza **150 000 zł**; wcześniejsza wypłata wynosi **110 000 zł**.

**Przyczyna:** zdanie o braku podstaw do przyznania pełnej żądanej kwoty potraktowano jako całkowite oddalenie. Similarity wyniosło 0,886. Uzasadnienie obniżenia żądania nie jest dowodem braku jakiegokolwiek świadczenia.

**Proponowane rozwiązanie:** odfiltrować jako pełny denial sformułowania „w kwocie zażądanej”, „w pozostałej części”, „ponad kwotę” i „dalej idące żądanie”. Rozszerzyć wzorce `mixed` o takie przypadki. Najpierw sprawdzić dodatnie zasądzenie z sentencji. Przy wcześniejszej wypłacie preferować jawne podsumowanie 110 000 zł, zamiast dodawać do niego ponownie wcześniejsze części tej samej wypłaty.

### 369009 — I C 537/16

**Opis:** zapisano `total=30000`. Sentencja zasądza **170 000 zł = 30 000 zł odszkodowania + 140 000 zł zadośćuczynienia**. Wcześniejsze świadczenia uwzględnione przy zadośćuczynieniu to **60 000 zł = 40 000 + 20 000**, a zapisano zero.

**Przyczyna:** wybrano tylko jeden składnik. Drugą klauzulę skierowano do odsetek, ponieważ obok kwoty głównej wymieniała również kwoty stanowiące podstawę naliczania odsetek.

**Proponowane rozwiązanie:** w każdym punkcie „zasądza ... kwotę ...” najpierw wyodrębnić świadczenie główne. Dalszy tekst „z odsetkami ... od kwoty ...” odciąć od parsowania kolejnych składników targetu. Dodać wzorzec takiej klauzuli do bazy `judgment`, a następnie zsumować dwa główne świadczenia. Nie dodawać drugi raz podstaw naliczania odsetek ani wcześniejszych wypłat.

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
