"""
Descarga pinturas de dominio público del Art Institute of Chicago (ARTIC),
traduce todos los campos al castellano y genera paintings.json.

API gratuita, sin autenticación, >1700 pinturas con imagen y metadatos.
Documentación: https://api.artic.edu/docs/

Uso:
    python scripts/fetch_met_museum.py            # descarga todo + traduce
    python scripts/fetch_met_museum.py --solo-procesar   # usa _raw.json ya descargado

Genera: backend/app/data/paintings.json
"""

import argparse
import json
import re
import time
from pathlib import Path

import requests
from tqdm import tqdm

ARTIC_API = "https://api.artic.edu/api/v1"
ARTIC_IMAGE = "https://www.artic.edu/iiif/2/{image_id}/full/600,/0/default.jpg"
OUTPUT_PATH = Path(__file__).parent.parent / "app" / "data" / "paintings.json"
RAW_PATH = Path(__file__).parent.parent / "app" / "data" / "_raw.json"

FIELDS = ",".join([
    "id", "title", "artist_display", "date_end", "date_display",
    "style_title", "place_of_origin", "image_id", "department_title",
    "is_public_domain", "artwork_type_title", "medium_display",
])
HEADERS = {"User-Agent": "ArtQuizApp/1.0 (educational project)"}

# ---------------------------------------------------------------------------
# Movimiento / style_title
# ---------------------------------------------------------------------------
MOVIMIENTOS: dict[str, str] = {
    "19th century": "Siglo XIX",
    "nineteenth century": "Siglo XIX",
    "18th Century": "Siglo XVIII",
    "eighteenth century": "Siglo XVIII",
    "17th Century": "Barroco",
    "seventeenth century": "Barroco",
    "16th Century": "Renacimiento",
    "sixteenth century": "Renacimiento",
    "15th century": "Siglo XV",
    "fifteenth century": "Siglo XV",
    "14th century": "Siglo XIV",
    "fourteenth century": "Siglo XIV",
    "13th century": "Siglo XIII",
    "20th Century": "Siglo XX",
    "Impressionism": "Impresionismo",
    "Post-Impressionism": "Postimpresionismo",
    "Realism": "Realismo",
    "Renaissance": "Renacimiento",
    "Baroque": "Barroco",
    "Mannerism": "Manierismo",
    "Neoclassicism": "Neoclasicismo",
    "Modernism": "Modernismo",
    "Symbolism": "Simbolismo",
    "Romanticism": "Romanticismo",
    "Pre-Raphaelite": "Prerrafaelismo",
    "Pointillism": "Puntillismo",
    "Expressionism": "Expresionismo",
    "Surrealism": "Surrealismo",
    "Cubism": "Cubismo",
    "Fauvism": "Fauvismo",
    "Abstract Expressionism": "Expresionismo Abstracto",
    "Minimalism": "Minimalismo",
    "Pop Art": "Arte Pop",
    "Folk Art": "Arte Popular",
    "Barbizon School": "Escuela de Barbizon",
    "Hudson River School": "Escuela del Río Hudson",
    "synthetist": "Sintetismo",
    "chinese (culture or style)": "Arte Chino",
    "Chinese (culture or style)": "Arte Chino",
    "japanese (culture or style)": "Arte Japonés",
    "Japanese (culture or style)": "Arte Japonés",
    "Korean (culture or style)": "Arte Coreano",
    "South Asian": "Arte del Sur de Asia",
    "Indian (South Asian)": "Arte Indio",
    "Himalayan": "Arte Himalayo",
    "Islamic (culture or style)": "Arte Islámico",
    "mughal": "Arte Mogol",
    "safavid": "Arte Safávida",
    "saffarid": "Arte Safárida",
    "isfahan": "Escuela de Isfahán",
    "edo (japanese period)": "Período Edo",
    "muromachi": "Período Muromachi",
    "american colonial": "Colonial Americano",
    "european": "Arte Europeo",
    "dutch": "Arte Holandés",
    "Flemish": "Arte Flamenco",
    "france": "Arte Francés",
    "hungarian": "Arte Húngaro",
    "ancient": "Arte Antiguo",
    "new kingdom": "Antiguo Egipto",
    "third intermediate period": "Antiguo Egipto",
    "lakota": "Arte Lakota",
    "cheyenne": "Arte Cheyenne",
    "gondar": "Arte de Gondar",
    "yüan": "Dinastía Yuan",
}

# Fallback por department_title
DEPARTAMENTOS: dict[str, str] = {
    "Painting and Sculpture of Europe": "Arte Europeo",
    "American Art": "Arte Americano",
    "Asian Art": "Arte Asiático",
    "Medieval to Modern European Painting": "Arte Europeo",
    "Modern and Contemporary Art": "Arte Contemporáneo",
    "African Art": "Arte Africano",
    "Ancient Art": "Arte Antiguo",
    "Arms and Armor": "Arte Decorativo",
    "Indian Art of the Americas": "Arte de las Américas",
    "Art of the Ancient Mediterranean World": "Arte Mediterráneo Antiguo",
    "Arts of Africa": "Arte Africano",
    "Textiles": "Textil",
    "Photography": "Fotografía",
    "Prints and Drawings": "Grabado y Dibujo",
}

# ---------------------------------------------------------------------------
# Tipo / medium_display
# ---------------------------------------------------------------------------
TIPOS: dict[str, str] = {
    "Oil on canvas": "Óleo sobre lienzo",
    "Oil on panel": "Óleo sobre tabla",
    "Oil on wood": "Óleo sobre madera",
    "Oil on board": "Óleo sobre tablero",
    "Oil on copper": "Óleo sobre cobre",
    "Oil on vellum": "Óleo sobre vitela",
    "Oil on cardboard": "Óleo sobre cartón",
    "Oil on paper": "Óleo sobre papel",
    "Oil on linen": "Óleo sobre lino",
    "Oil on silk": "Óleo sobre seda",
    "Oil on mahogany panel": "Óleo sobre tabla de caoba",
    "Oil on yellow poplar panel": "Óleo sobre tabla de álamo amarillo",
    "Oil on cradled panel": "Óleo sobre tabla con bastidor",
    "Oil on jute canvas": "Óleo sobre lienzo de yute",
    "Oil on linen canvas": "Óleo sobre lienzo de lino",
    "Oil on composition board": "Óleo sobre tablero compuesto",
    "Oil on paper, mounted on canvas": "Óleo sobre papel, montado en lienzo",
    "Oil on canvas, mounted on board": "Óleo sobre lienzo, montado en tablero",
    "Oil and tempera on panel": "Óleo y témpera sobre tabla",
    "Tempera and oil on panel": "Témpera y óleo sobre tabla",
    "Tempera on panel": "Témpera sobre tabla",
    "Tempera on panel, transferred to canvas": "Témpera sobre tabla, transferida a lienzo",
    "Tempera or oil on panel": "Témpera u óleo sobre tabla",
    "Tempera with oil glazes on panel": "Témpera con veladuras de óleo sobre tabla",
    "Oil on panel, transferred to canvas": "Óleo sobre tabla, transferido a lienzo",
    "Encaustic on canvas": "Encáustica sobre lienzo",
    "Fresco": "Fresco",
    "Watercolor on paper": "Acuarela sobre papel",
    "Watercolor and gouache on paper": "Acuarela y gouache sobre papel",
    "Gouache on paper": "Gouache sobre papel",
    "Ink on paper": "Tinta sobre papel",
    "Ink and watercolor on paper": "Tinta y acuarela sobre papel",
    "Ink and color on paper": "Tinta y color sobre papel",
    "Ink and color on silk": "Tinta y color sobre seda",
    "Ink, colors, and gold on silk": "Tinta, colores y oro sobre seda",
    "Ink and opaque watercolor on paper": "Tinta y acuarela opaca sobre papel",
    "Colors on paper": "Colores sobre papel",
    "Colors on silk": "Colores sobre seda",
    "Opaque watercolor on paper": "Acuarela opaca sobre papel",
    "Opaque watercolor and gold on paper": "Acuarela opaca y oro sobre papel",
    "Opaque watercolor, gold, and ink on paper": "Acuarela opaca, oro e tinta sobre papel",
    "Opaque watercolor and ink on paper": "Acuarela opaca e tinta sobre papel",
    "Opaque and translucent watercolor on pith paper": "Acuarela opaca y translúcida sobre papel de médula",
    "Ink and color on hemp cloth": "Tinta y color sobre tela de cáñamo",
    "Pigment on cloth": "Pigmento sobre tela",
    "Pigments and metallic paint on wood": "Pigmentos y pintura metálica sobre madera",
    "Pigment and gold on cotton": "Pigmento y oro sobre algodón",
    "Pastel on paper": "Pastel sobre papel",
    "Pastel on canvas": "Pastel sobre lienzo",
    "Drawing": "Dibujo",
    "Charcoal on paper": "Carboncillo sobre papel",
    "Pencil on paper": "Lápiz sobre papel",
    "Hanging scroll": "Rollo colgante",
    "Handscroll": "Rollo manual",
    "Album leaf": "Hoja de álbum",
    "Album leaves": "Hojas de álbum",
    "Album of 25 leaves": "Álbum de 25 hojas",
    "Fan painting": "Pintura en abanico",
    "Pair of six-panel screens": "Par de biombos de seis paneles",
    "Pair of six panel screens": "Par de biombos de seis paneles",
    "Pair of six-fold screens": "Par de biombos de seis hojas",
    "Six-panel screen": "Biombo de seis paneles",
    "Set of three hanging scrolls": "Conjunto de tres rollos colgantes",
    "Pair of hanging scrolls": "Par de rollos colgantes",
    "A pair of hanging scrolls": "Par de rollos colgantes",
    "Triptych of hanging scrolls": "Tríptico de rollos colgantes",
    "Folding fan mounted as an album leaf": "Abanico plegable montado como hoja de álbum",
    "Album leaf, inks and color on paper.": "Hoja de álbum, tintas y color sobre papel",
}

# ---------------------------------------------------------------------------
# Títulos / traducciones estáticas
# ---------------------------------------------------------------------------
TITULOS: dict[str, str] = {
    # A
    "A Battle Scene from a Shahnama Manuscript": "Escena de batalla de un manuscrito del Shahnama",
    "A Beauty Behind a Screen": "Una belleza tras una pantalla",
    "A Bishop Saint": "Un obispo santo",
    "A Boy Blowing on a Firebrand": "Un niño soplando un tizón",
    "A City Park": "Un parque de la ciudad",
    "A Clump of Trees": "Un grupo de árboles",
    "A Courtesan Reading a Letter": "Una cortesana leyendo una carta",
    "A Family Meal": "Una comida familiar",
    "A Farmhouse in the Bavarian Alps": "Una granja en los Alpes bávaros",
    "A Friendly Warning": "Una advertencia amistosa",
    "A Glimpse into Hell, or Fear": "Un vistazo al infierno, o el miedo",
    "A Holiday": "Un día festivo",
    "A Lady": "Una dama",
    "A Lady Reading (Saint Mary Magdalene)": "Una dama leyendo (Santa María Magdalena)",
    "A Lamplight Study: Herr Joachim": "Estudio a la luz de la lámpara: Herr Joachim",
    "A Marine": "Una marina",
    "A Mexican Vaquero": "Un vaquero mexicano",
    "A Monumental Portrait of a Monkey": "Retrato monumental de un mono",
    "A Mother Feeding her Child (The Happy Mother)": "Una madre alimentando a su hijo (La madre feliz)",
    "A Mounted Officer": "Un oficial montado",
    "A Pair of Carp": "Un par de carpas",
    "A Peasant Woman Digging in Front of Her Cottage": "Una campesina cavando frente a su cabaña",
    "A Roadside Tavern": "Una taberna al borde del camino",
    "A Silver Morning": "Una mañana plateada",
    "A Stream in France": "Un arroyo en Francia",
    "A Sunday on La Grande Jatte — 1884": "Un domingo en La Grande Jatte — 1884",
    "A Turn in the Road": "Un recodo del camino",
    "A Vanitas Still Life with a Flag, Candlestick, Musical Instruments, Books, Writing Paraphernalia, Globes, and Hourglass": "Vanitas con bandera, candelabro, instrumentos musicales, libros, utensilios de escritura, globos y reloj de arena",
    "A View of Vianen with a Herdsman and Cattle by a River": "Vista de Vianen con un pastor y ganado junto a un río",
    "A Witches' Sabbath": "El aquelarre",
    "A Woman at the Élysée Montmartre (Femme à l'Élysée Montmartre)": "Una mujer en el Élysée Montmartre",
    "A Young Prince on Horseback": "Un joven príncipe a caballo",
    "Abduction of the Sabines": "El rapto de las Sabinas",
    "Abraham's Sacrifice of Isaac": "El sacrificio de Isaac por Abrahán",
    "Acrobats at the Cirque Fernando (Francisca and Angelina Wartenberg)": "Acróbatas en el Cirque Fernando (Francisca y Angelina Wartenberg)",
    "Adam": "Adán",
    "Adam and Eve in Paradise": "Adán y Eva en el Paraíso",
    "Adoration of the Magi": "La Adoración de los Reyes Magos",
    "After a Summer Shower": "Después de un aguacero de verano",
    "After the Bullfight": "Después de la corrida",
    "Afterglow": "Resplandor del crepúsculo",
    "Afternoon Tea": "Té de la tarde",
    "Allegory of Charity": "Alegoría de la Caridad",
    "Allegory of Peace and War": "Alegoría de la Paz y la Guerra",
    "Allegory of Venus and Cupid": "Alegoría de Venus y Cupido",
    "Alpine Scene": "Escena alpina",
    "An Abundance of Fruit": "Una abundancia de fruta",
    "An Actor on Stage": "Un actor en escena",
    "An Elegant Company": "Una compañía elegante",
    "An Italian Comedy in Verona": "Una comedia italiana en Verona",
    "An Old Man in a Fur Cap": "Un anciano con gorro de piel",
    "Annunciation to the Shepherds": "Anunciación a los pastores",
    "Apples": "Manzanas",
    "Apples and Grapes": "Manzanas y uvas",
    "Approaching Storm": "Tormenta que se acerca",
    "Arab Horseman Attacked by a Lion": "Jinete árabe atacado por un león",
    "Arcadian Landscape with Figures": "Paisaje arcádico con figuras",
    "Armida Abandoned by Rinaldo": "Armida abandonada por Rinaldo",
    "Armida Encounters the Sleeping Rinaldo": "Armida encuentra a Rinaldo dormido",
    "Arrangement in Flesh Color and Brown: Portrait of Arthur Jerome Eddy": "Composición en color carne y marrón: Retrato de Arthur Jerome Eddy",
    "Arrival of the Normandy Train, Gare Saint-Lazare": "Llegada del tren de Normandía, Gare Saint-Lazare",
    "At the Circus: The Bareback Rider (Au Cirque: Écuyère)": "En el circo: la amazona",
    "Autumn Maples with Poem Slips": "Arces otoñales con tiras de poemas",
    "Autumn Woods": "Bosque otoñal",
    "Auvers, Panoramic View": "Auvers, vista panorámica",
    # B
    "Bamboo-Covered Stream in Spring Rain": "Arroyo entre bambúes en la lluvia primaveral",
    "Beggar with Oysters (Philosopher)": "Mendigo con ostras (Filósofo)",
    "Beggar with a Duffle Coat (Philosopher)": "Mendigo con abrigo (Filósofo)",
    "Bird's Nest and Ferns": "Nido de pájaro y helechos",
    "Birth of Bacchus": "Nacimiento de Baco",
    "Boats at Rest": "Barcas en reposo",
    "Boats on the Beach at Étretat": "Barcas en la playa de Étretat",
    "Boy of Hallett Family with Dog": "Niño de la familia Hallett con perro",
    "Boy on a Ram": "Niño sobre un carnero",
    "Boy with Pitcher (La Régalade)": "Niño con jarra",
    "Branch of the Seine near Giverny (Mist)": "Brazo del Sena cerca de Giverny (Niebla)",
    "Bullfight": "Corrida de toros",
    # C
    "Cabin in the Cotton": "Cabaña entre el algodón",
    "Calf's Head and Ox Tongue": "Cabeza de ternera y lengua de buey",
    "Catskill Mountains": "Montañas Catskill",
    "Ceremony of the Fastest Horse": "Ceremonia del caballo más veloz",
    "Charing Cross Bridge, London": "Puente de Charing Cross, Londres",
    "Christ Carrying the Cross": "Cristo portando la Cruz",
    "Christ Washing the Feet of His Disciples": "Cristo lavando los pies de sus discípulos",
    "Christ on the Living Cross": "Cristo en la Cruz viviente",
    "Chrysanthemums": "Crisantemos",
    "Cliff Walk at Pourville": "Paseo por los acantilados de Pourville",
    "Coast Scene, Bathers": "Escena costera, bañistas",
    "Colonnade and Gardens of the Medici Palace": "Columnata y jardines del Palacio Médici",
    "Crucifixion": "Crucifixión",
    # D
    "Daniel Saving Susanna, the Judgment of Daniel, and the Execution of the Elders": "Daniel salvando a Susana, el juicio de Daniel y la ejecución de los ancianos",
    "Dedication (Odes and Sonnets)": "Dedicatoria (Odas y Sonetos)",
    "Deposition": "El Descendimiento",
    "Distant View of Niagara Falls": "Vista lejana de las cataratas del Niágara",
    "Don Quixote and the Windmills": "Don Quijote y los molinos de viento",
    "Drinking at Night": "Bebiendo de noche",
    # E
    "Early Morning, Tarpon Springs": "Primera mañana en Tarpon Springs",
    "Emperor Heraclius Denied Entry into Jerusalem": "El emperador Heraclio rechazado en Jerusalén",
    "Equestrienne (At the Cirque Fernando)": "Amazona (En el Cirque Fernando)",
    # F
    "Fish": "Pez",
    "Fish (Still Life)": "Pez (Naturaleza muerta)",
    "Fishing Boats with Hucksters Bargaining for Fish": "Barcas de pesca con buhoneros regateando el pescado",
    "Flight of Geese": "Vuelo de gansos",
    "Flower Arrangements": "Composiciones florales",
    "Flowers and Fruit in a Chinese Bowl": "Flores y fruta en un cuenco chino",
    "Flowers of the Four Seasons": "Flores de las cuatro estaciones",
    "For Sunday's Dinner": "Para la cena del domingo",
    "Fountain and Pergola in Italy": "Fuente y pérgola en Italia",
    "Fruit Piece": "Naturaleza muerta con frutas",
    "Fruits of the Midi": "Frutos del Mediodía",
    # G
    "Ghost Dance (The Vision of Life)": "Danza de los Espíritus (La visión de la vida)",
    "Girl with Cherries": "Niña con cerezas",
    "Grapes, Lemons, Pears, and Apples": "Uvas, limones, peras y manzanas",
    "Grey and Silver: Old Battersea Reach": "Gris y plata: antiguo tramo de Battersea",
    # H
    "Harvest, Montclair, New Jersey": "Cosecha, Montclair, Nueva Jersey",
    "Haymaking at Éragny": "Henificación en Éragny",
    "Head of a Philosopher": "Cabeza de filósofo",
    "Hercules and the Lernaean Hydra": "Hércules y la Hidra de Lerna",
    "Houses of Parliament, London": "Parlamento de Londres",
    "Houses on the Fox River, Illinois": "Casas junto al río Fox, Illinois",
    "Ice-Bound Falls": "Cascadas heladas",
    "Icebound": "Atrapado por el hielo",
    "Improvisation No. 30 (Cannons)": "Improvisación n.º 30 (Cañones)",
    "In the Auvergne": "En la Auvernia",
    "In the Café": "En el café",
    "Inside the Colosseum": "Interior del Coliseo",
    "Interior of St. Mark's, Venice": "Interior de San Marcos, Venecia",
    "Irises": "Lirios",
    "Italian Landscape": "Paisaje italiano",
    # J
    "Jean Renoir Sewing": "Jean Renoir cosiendo",
    "Jesus Mocked by the Soldiers": "Jesús burlado por los soldados",
    "Judith with the Head of Holofernes": "Judit con la cabeza de Holofernes",
    # K
    "Keats' Last Sonnet": "El último soneto de Keats",
    # L
    "Lady Reading the Letters of Heloise and Abelard": "Dama leyendo las cartas de Eloísa y Abelardo",
    "Lady Sarah Bunbury Sacrificing to the Graces": "Lady Sarah Bunbury sacrificando a las Gracias",
    "Landscape": "Paisaje",
    "Landscape (The Lock)": "Paisaje (La esclusa)",
    "Landscape Painting": "Pintura de paisaje",
    "Landscape near Chiusi, Tuscany": "Paisaje cerca de Chiusi, Toscana",
    "Landscape with Saint John on Patmos": "Paisaje con San Juan en Patmos",
    "Landscape with the Ruins of the Castle of Egmond": "Paisaje con las ruinas del castillo de Egmond",
    "Landscape, Sunset": "Paisaje al atardecer",
    "Lights of Other Days": "Luces de otros tiempos",
    "Lion Hunt": "La caza del león",
    "Lozenge Composition with Yellow, Black, Blue, Red, and Gray": "Composición en rombo con amarillo, negro, azul, rojo y gris",
    "Lucie Berard (Child in White)": "Lucie Berard (Niña de blanco)",
    "Lunch at the Restaurant Fournaise (The Rowers' Lunch)": "Almuerzo en el restaurante Fournaise (El almuerzo de los remeros)",
    # M
    "Madame Cezanne in a Yellow Chair": "Madame Cézanne en una silla amarilla",
    "Madame de Pastoret and Her Son": "Madame de Pastoret y su hijo",
    "Madonna and Child with Saints Elizabeth and John the Baptist": "Virgen con el Niño, Santa Isabel y San Juan Bautista",
    "Man in Black": "Hombre de negro",
    "Margaret of Austria, Queen of Spain": "Margarita de Austria, reina de España",
    "Moonrise": "Salida de la luna",
    "Morning": "Mañana",
    "Mountain Brook": "Arroyo de montaña",
    # N
    "Near the Lake": "Junto al lago",
    "New England Headlands": "Acantilados de Nueva Inglaterra",
    "New England Scenery": "Paisaje de Nueva Inglaterra",
    "Nicolas Rubens, the Artist's Son": "Nicolás Rubens, hijo del artista",
    "Nocturne: Blue and Gold—Southampton Water": "Nocturno: azul y oro — aguas de Southampton",
    "Nothing But Cheerful Looks Followed the Bat": "Solo miradas alegres siguieron al murciélago",
    # O
    "Odalisque": "Odalisca",
    "Old Man with a Gold Chain": "Anciano con cadena de oro",
    "Old Tower at Avignon": "Torre antigua en Aviñón",
    "On a Balcony": "En un balcón",
    "On the Bank of the Seine, Bennecourt": "A orillas del Sena, Bennecourt",
    "Orchids": "Orquídeas",
    # P
    "Panels from the High Altar of the Charterhouse of Saint-Honoré, Thuison-les-Abbeville: Pentecost": "Paneles del altar mayor de la Cartuja de Saint-Honoré: Pentecostés",
    "Pardon in Brittany": "Perdón en Bretaña",
    "Paris Street; Rainy Day": "Calle de París; Día lluvioso",
    "Pastoral Scene": "Escena pastoral",
    "Peasant Family at a Well": "Familia campesina junto a un pozo",
    "Peasants Bringing Home a Calf Born in the Fields": "Campesinos llevando a casa un ternero nacido en los campos",
    "Peonies, Magnolia, and Dandelions": "Peonías, magnolia y dientes de león",
    "Pergola with Oranges": "Pérgola con naranjos",
    "Pillars of the Country": "Pilares del país",
    "Polynesian Woman with Children": "Mujer polinesia con niños",
    "Pond in the Woods": "Estanque en el bosque",
    "Poppy Field (Giverny)": "Campo de amapolas (Giverny)",
    "Portrait of Cardinal Zelada": "Retrato del cardenal Zelada",
    "Portrait of Constance Pipelet": "Retrato de Constance Pipelet",
    "Portrait of Dr. William McNeill Whistler": "Retrato del Dr. William McNeill Whistler",
    "Portrait of Emmanuel Rio": "Retrato de Emmanuel Rio",
    "Portrait of Louise de Halluin, dame de Cipierre": "Retrato de Louise de Halluin, dama de Cipierre",
    "Portrait of a Gentleman": "Retrato de un caballero",
    "Portrait of a Girl with a Dog": "Retrato de una niña con perro",
    "Portrait of a Man": "Retrato de un hombre",
    "Portrait of a Man in Costume": "Retrato de un hombre disfrazado",
    "Portrait of a Man with a Pink": "Retrato de un hombre con un clavel",
    "Portrait of a Musician": "Retrato de un músico",
    "Portrait of a Woman": "Retrato de una mujer",
    "Portrait of a Woman with a Black Fichu": "Retrato de una mujer con fichu negro",
    "Portrait of a Young Woman": "Retrato de una mujer joven",
    "Portrait of an Artist": "Retrato de un artista",
    "Portrait of the Artist's Father, Ismael Mengs": "Retrato del padre del artista, Ismael Mengs",
    "Portrait of the Katchef Dahouth, Christian Mameluke": "Retrato del Katchef Dahouth, mameluco cristiano",
    "Portrait of the Princess di Ottaiano and her son Carlo": "Retrato de la princesa di Ottaiano y su hijo Carlo",
    "Prunus and Bamboo": "Ciruelo y bambú",
    # R
    "Rabbit Warren at Pontoise, Snow": "Madriguera de conejos en Pontoise, nieve",
    "Ravine Near Biskra": "Barranco cerca de Biskra",
    "Rebirth of the Nun Anyo": "Renacimiento de la monja Anyo",
    "Recluse Dwellings in the Autumn Mountains": "Moradas de ermitaños en las montañas otoñales",
    "Resting": "Descansando",
    "Retable and Frontal of the Life of Christ and the Virgin": "Retablo y frontal de la vida de Cristo y la Virgen",
    "Retable of Saints Athanasius, Blaise, and Agatha": "Retablo de los santos Atanasio, Blas y Águeda",
    "Rinaldo and Armida in Her Garden": "Rinaldo y Armida en su jardín",
    "Rinaldo and the Magus of Ascalon": "Rinaldo y el mago de Ascalón",
    "River and Mountain Landscape": "Paisaje de río y montaña",
    "Rocks at Port-Goulphar, Belle-Île": "Rocas en Port-Goulphar, Belle-Île",
    "Ruler Entertained by Dancers in a Paradise Garden": "Soberano entretenido por bailarines en un jardín paradisíaco",
    # S
    "Saint Andrew": "San Andrés",
    "Saint Francis Kneeling in Meditation": "San Francisco arrodillado en meditación",
    "Saint George and the Dragon": "San Jorge y el dragón",
    "Saint Jerome in Penitence": "San Jerónimo en penitencia",
    "Saint Jerome in the Wilderness": "San Jerónimo en el desierto",
    "Saint John the Baptist": "San Juan Bautista",
    "Saint John the Baptist Preaching in the Desert": "San Juan Bautista predicando en el desierto",
    "Saint John the Evangelist and Donor": "San Juan Evangelista y donante",
    "Saint Sebastian": "San Sebastián",
    "Salome with the Head of Saint John the Baptist": "Salomé con la cabeza de San Juan Bautista",
    "Sawmill, Outskirts of Paris": "Aserradero, afueras de París",
    "Scenes from the Life of Saint John the Baptist": "Escenas de la vida de San Juan Bautista",
    "Seated Bather": "Bañista sentada",
    "Self-Portrait": "Autorretrato",
    "Sketch for The Revolt of Cairo": "Boceto para La revuelta de El Cairo",
    "Sketch for a Ceiling Fresco": "Boceto para un fresco de techo",
    "Slave Market": "Mercado de esclavos",
    "Snow Field, Morning, Roxbury": "Campo nevado, mañana, Roxbury",
    "Snow at Louveciennes": "Nieve en Louveciennes",
    "Song of a Fisherman": "Canción de un pescador",
    "Spring in France": "Primavera en Francia",
    "Springtime": "Primavera",
    "Squirrel and Grapes": "Ardilla y uvas",
    "St. Joseph and Christ Child": "San José y el Niño Jesús",
    "Stack of Wheat": "Paca de trigo",
    "Stack of Wheat (Snow Effect, Overcast Day)": "Paca de trigo (efecto de nieve, día nublado)",
    "Stack of Wheat (Thaw, Sunset)": "Paca de trigo (deshielo, atardecer)",
    "Stacks of Wheat (End of Day, Autumn)": "Pacas de trigo (final del día, otoño)",
    "Stacks of Wheat (End of Summer)": "Pacas de trigo (fin del verano)",
    "Stacks of Wheat (Sunset, Snow Effect)": "Pacas de trigo (atardecer, efecto de nieve)",
    "Staircase in the Park of Villa Chigi di Ariccia": "Escalinata en el parque de la Villa Chigi di Ariccia",
    "Standing Bather, Seen from the Back": "Bañista de pie, vista de espaldas",
    "Still Life with Geranium": "Naturaleza muerta con geranio",
    "Still Life with Grapes and Flowers": "Naturaleza muerta con uvas y flores",
    "Still Life with Monkey, Fruits, and Flowers": "Naturaleza muerta con mono, frutas y flores",
    "Still Life: Wood Tankard and Metal Pitcher": "Naturaleza muerta: jarra de madera y pichel de metal",
    "Still Life—Strawberries, Nuts, &c.": "Naturaleza muerta — fresas, nueces, etc.",
    "Storm in Umbria": "Tormenta en Umbría",
    "Street in Moret": "Calle en Moret",
    "Study for \"Arrangement in Grey and Black, No. 2: Portrait of Thomas Carlyle\"": "Estudio para Composición en gris y negro, n.º 2: Retrato de Thomas Carlyle",
    "Study of Two Bedouins": "Estudio de dos beduinos",
    "Study of a Girl's Head and Shoulders": "Estudio de cabeza y hombros de una niña",
    "Sunlit Valley": "Valle iluminado por el sol",
    "Susanna and the Elders in the Garden, and the Trial of Susanna before the Elders": "Susana y los ancianos en el jardín, y el juicio de Susana ante los ancianos",
    # T
    "The Actor Maximilian Korn in a Landscape": "El actor Maximilian Korn en un paisaje",
    "The Adoration of the Magi": "La Adoración de los Magos",
    "The Adventures of Ulysses": "Las aventuras de Ulises",
    "The Annunciation": "La Anunciación",
    "The Apple Market": "El mercado de manzanas",
    "The Artist in His Studio": "El artista en su estudio",
    "The Artist's House at Argenteuil": "La casa del artista en Argenteuil",
    "The Assumption of the Virgin": "La Asunción de la Virgen",
    "The August Moon": "La luna de agosto",
    "The Banks of the Marne in Winter": "Las orillas del Marne en invierno",
    "The Basket of Apples": "La cesta de manzanas",
    "The Bathers": "Los bañistas",
    "The Battle of Pharsalus and the Death of Pompey": "La batalla de Farsalia y la muerte de Pompeyo",
    "The Bay of Marseille, Seen from L'Estaque": "La bahía de Marsella, vista desde L'Estaque",
    "The Beach at Sainte-Adresse": "La playa de Sainte-Adresse",
    "The Beautiful Greek Woman": "La bella griega",
    "The Bedroom": "El dormitorio",
    "The Beggar Boy (The Young Pilgrim)": "El niño mendigo (el joven peregrino)",
    "The Beheading of Saint John the Baptist": "La decapitación de San Juan Bautista",
    "The Captive Slave (Ira Aldridge)": "El esclavo cautivo (Ira Aldridge)",
    "The Child's Bath": "El baño del niño",
    "The Combat of the Giaour and Hassan": "El combate del Giaour y Hassan",
    "The Continence of Scipio": "La continencia de Escipión",
    "The Conversation": "La conversación",
    "The Crucifixion": "La Crucifixión",
    "The Crystal Palace": "El Palacio de Cristal",
    "The Customs House at Varengeville": "La aduana de Varengeville",
    "The Denial of Saint Peter": "La negación de San Pedro",
    "The Departure of the Boats, Étretat": "La partida de los barcos, Étretat",
    "The Dream of Saint Jerome": "El sueño de San Jerónimo",
    "The Dreamer (La Rêveuse)": "La soñadora",
    "The Earl of Coventry's Horse": "El caballo del conde de Coventry",
    "The Entombment": "El Descendimiento",
    "The Eruption of Vesuvius": "La erupción del Vesubio",
    "The Fairies": "Las hadas",
    "The Family Concert": "El concierto familiar",
    "The Fates Gathering in the Stars": "Las Parcas reunidas entre las estrellas",
    "The Feast in the House of Simon": "El banquete en casa de Simón",
    "The Fire Eater Raised His Arms to the Thunder Bird": "El tragafuegos alzó los brazos hacia el pájaro del trueno",
    "The Five Virtues": "Las cinco virtudes",
    "The Fountain at Grottaferrata": "La fuente de Grottaferrata",
    "The Fountain, Villa Torlonia, Frascati, Italy": "La fuente, Villa Torlonia, Frascati, Italia",
    "The Fountains": "Las fuentes",
    "The Garden of Palazzo Contarini dal Zaffo": "El jardín del Palazzo Contarini dal Zaffo",
    "The Girl by the Window": "La niña junto a la ventana",
    "The Grand Canal, Venice": "El Gran Canal, Venecia",
    "The Grey Bodice": "El corpino gris",
    "The Herring Net": "La red de arenques",
    "The Holy Family with Saints Elizabeth and John the Baptist": "La Sagrada Familia con Santa Isabel y San Juan Bautista",
    "The Imperial Palace on the Palatine, Rome": "El Palacio Imperial en el Palatino, Roma",
    "The Irish Question": "La cuestión irlandesa",
    "The Keeper of the Flock": "El guardián del rebaño",
    "The Landing Place": "El embarcadero",
    "The Last of New England—The Beginning of New Mexico": "El último rincón de Nueva Inglaterra — El comienzo de Nuevo México",
    "The Laundress": "La lavandera",
    "The Lion Hunt": "La caza del león",
    "The Lonely Farm, Nantucket": "La granja solitaria, Nantucket",
    "The Madonna with the Seven Founders of the Servite Order": "La Virgen con los siete fundadores de la Orden de los Servitas",
    "The Marsh": "El pantano",
    "The Meeting of Gautier, Count of Antwerp, and his Daughter, Violante": "El encuentro de Gautier, conde de Amberes, y su hija Violante",
    "The Millinery Shop": "La sombrerería",
    "The Moon at Night": "La luna de noche",
    "The Movings": "La mudanza",
    "The Music Lesson": "La lección de música",
    "The Nativity": "La Natividad",
    "The Obelisk": "El obelisco",
    "The Old Temple": "El templo antiguo",
    "The Petite Creuse River": "El río Petite Creuse",
    "The Place du Havre, Paris": "La Place du Havre, París",
    "The Plate of Apples": "El plato de manzanas",
    "The Poet's Garden": "El jardín del poeta",
    "The Races at Longchamp": "Las carreras en Longchamp",
    "The Rock of Hautepierre": "La roca de Hautepierre",
    "The Sand Pits, Hampstead Heath": "Los arenales de Hampstead Heath",
    "The Scullion": "El fregaplatos",
    "The Shadow of Death": "La sombra de la muerte",
    "The Song of the Lark": "El canto de la alondra",
    "The Squirrel": "La ardilla",
    "The Storm": "La tormenta",
    "The Valley of Les Puits-Noir": "El valle de Les Puits-Noir",
    "The Vase of Tulips": "El jarrón de tulipanes",
    "The Wedding at Cana": "Las bodas de Caná",
    "The White Bridge": "El puente blanco",
    "The White Tablecloth": "El mantel blanco",
    "The Young Emperor Akbar Arrests the Insolent Shah Abu'l-Maali, Page from a Manuscript of the Akbarnama": "El joven emperador Akbar arresta al insolente Shah Abu'l-Maali, página de un manuscrito del Akbarnama",
    "Theodosius Repulsed from the Church by Saint Ambrose": "Teodosio rechazado de la iglesia por San Ambrosio",
    "This Little Pig Went to Market": "Este cerdito fue al mercado",
    "Thistles": "Cardos",
    "Threatening": "Amenazante",
    "Time Unveiling Truth": "El tiempo descubriendo la verdad",
    "Travellers Arriving at an Inn": "Viajeros llegando a una posada",
    "Trompe-l'Oeil Still Life with a Flower Garland and a Curtain": "Trampantojo con guirnalda de flores y cortina",
    "Two Cows and a Young Bull beside a Fence in a Meadow": "Dos vacas y un toro joven junto a una valla en un prado",
    "Two Sisters (On the Terrace)": "Dos hermanas (En la terraza)",
    # V
    "Valley of Aosta: Snowstorm, Avalanche, and Thunderstorm": "Valle de Aosta: ventisca, avalancha y tormenta",
    "Venetian Glass Workers": "Sopladores de vidrio venecianos",
    "Venus, Cupid and Ceres": "Venus, Cupido y Ceres",
    "View of Cotopaxi": "Vista del Cotopaxi",
    "View of Genoa": "Vista de Génova",
    "View of Pirna with the Fortress of Sonnenstein": "Vista de Pirna con la fortaleza de Sonnenstein",
    "View of Saleve, near Geneva": "Vista del Salève, cerca de Ginebra",
    "View on the Grounds of a Villa near Florence": "Vista de los jardines de una villa cerca de Florencia",
    "View on the River Roseau, Dominica": "Vista del río Roseau, Dominica",
    "Violet and Silver—The Deep Sea": "Violeta y plata — El mar profundo",
    "Virgil Reading the \"Aeneid\" to Augustus, Octavia, and Livia": "Virgilio leyendo la Eneida a Augusto, Octavia y Livia",
    "Virgin and Child": "Virgen con el Niño",
    "Virgin and Child with Saints Dominic and Hyacinth": "Virgen con el Niño, Santo Domingo e Hiácinto",
    "Virgin and Child with Two Angels": "Virgen con el Niño y dos ángeles",
    "Virgin and Child with the Young Saint John the Baptist": "Virgen con el Niño y el joven San Juan Bautista",
    # W
    "Washing the Elephant": "Bañando al elefante",
    "Water Carriers on the Nile": "Aguadoras en el Nilo",
    "Water Lilies": "Nenúfares",
    "Water Lily Pond": "Estanque de nenúfares",
    "Watering Place at Marly": "Abrevadero en Marly",
    "Waterloo Bridge, Gray Weather": "Puente de Waterloo, tiempo gris",
    "Waterloo Bridge, Sunlight Effect": "Puente de Waterloo, efecto de luz solar",
    "Wind-Swept Sands": "Arenas barridas por el viento",
    "Woman Bathing Her Feet in a Brook": "Mujer bañando sus pies en un arroyo",
    "Woman Mending": "Mujer remendando",
    "Woman Reading": "Mujer leyendo",
    "Woman and Child at the Well": "Mujer y niño junto al pozo",
    "Woman at Her Toilette": "Mujer en su tocador",
    "Woman at the Piano": "Mujer al piano",
    "Woman before an Aquarium": "Mujer ante un acuario",
    "Woman in Front of a Still Life by Cezanne": "Mujer ante una naturaleza muerta de Cézanne",
    "Woman in a Garden": "Mujer en un jardín",
    "Woman on Rose Divan": "Mujer en un diván rosa",
    "Women Viewing Paintings": "Mujeres contemplando pinturas",
    # Y
    "Young Clergyman Reading": "Joven clérigo leyendo",
    "Young Man in a Turban": "Joven con turbante",
    "Young Peasant Having Her Coffee": "Joven campesina tomando su café",
    "Young Woman": "Mujer joven",
    "Young Woman Sewing": "Mujer joven cosiendo",
    "Young Woman at an Open Half-Door": "Mujer joven en una puerta entreabierta",
    # Additional entries
    "Abigail Chesebrough (Mrs. Alexander Grant)": "Abigail Chesebrough (Sra. de Alexander Grant)",
    "Abigail Inskeep Bradford": "Abigail Inskeep Bradford",
    "Ad Astra": "Ad Astra",
    "Aeneas Rescuing Anchises from Burning Troy": "Eneas rescatando a Anquises de la Troya en llamas",
    "African Chief": "Jefe africano",
    "After a Summer Shower": "Después de un aguacero de verano",
    "After the Bullfight": "Después de la corrida",
    "Alpheus and Arethusa": "Alfeo y Aretusa",
    "Antiochus Yearning for Stratonice": "Antíoco suspirando por Estratónice",
    "Apollo Granting Phaeton Permission to Drive the Chariot of the Sun": "Apolo concediendo permiso a Faetón para conducir el carro del sol",
    "Apollo and Marsyas": "Apolo y Marsias",
    "Appenine Landscape": "Paisaje de los Apeninos",
    "Architectural Landscape with Belisarius Receiving Alms": "Paisaje arquitectónico con Belisario recibiendo limosnas",
    "Autumn": "Otoño",
    "Autumn Landscape": "Paisaje otoñal",
    "Bathers": "Bañistas",
    "Battle Scene": "Escena de batalla",
    "Birth of Venus": "El nacimiento de Venus",
    "Bouquet of Flowers": "Ramo de flores",
    "By the Water": "Junto al agua",
    "Christ in the Garden of Gethsemane": "Cristo en el huerto de Getsemaní",
    "Children Playing": "Niños jugando",
    "Country Road": "Camino rural",
    "Dancers": "Bailarinas",
    "Edge of the Forest": "Al borde del bosque",
    "Exotic Landscape": "Paisaje exótico",
    "Farmyard": "Patio de granja",
    "Figures in a Landscape": "Figuras en un paisaje",
    "Figures on the Beach": "Figuras en la playa",
    "Floral Still Life": "Naturaleza muerta floral",
    "Flowers": "Flores",
    "Flowers in a Vase": "Flores en un jarrón",
    "Forest Interior": "Interior de bosque",
    "Forest Landscape": "Paisaje forestal",
    "Fruit": "Fruta",
    "Garden Scene": "Escena de jardín",
    "Girls": "Niñas",
    "Harbor Scene": "Escena portuaria",
    "Head of a Man": "Cabeza de hombre",
    "Head of a Woman": "Cabeza de mujer",
    "Head of a Young Woman": "Cabeza de mujer joven",
    "Historical Scene": "Escena histórica",
    "Houses in the Snow": "Casas en la nieve",
    "Interior": "Interior",
    "Interior with Figures": "Interior con figuras",
    "Landscape with Cattle": "Paisaje con ganado",
    "Landscape with Figures": "Paisaje con figuras",
    "Landscape with Mountains": "Paisaje con montañas",
    "Landscape with River": "Paisaje con río",
    "Landscape with Trees": "Paisaje con árboles",
    "Landscape with Water": "Paisaje con agua",
    "Market Scene": "Escena de mercado",
    "Moonlight": "Claro de luna",
    "Mother and Child": "Madre e hijo",
    "Mountain Landscape": "Paisaje de montaña",
    "Mountains": "Montañas",
    "Night Scene": "Escena nocturna",
    "Nude": "Desnudo",
    "Peasant Scene": "Escena campesina",
    "Peasants": "Campesinos",
    "Picking Flowers": "Recogiendo flores",
    "Reading": "Leyendo",
    "River Landscape": "Paisaje fluvial",
    "River Scene": "Escena fluvial",
    "Riverside": "Orilla del río",
    "Rural Scene": "Escena rural",
    "Sea": "El mar",
    "Seascape": "Marina",
    "Sewing": "Cosiendo",
    "Snow Scene": "Escena de nieve",
    "Spring": "Primavera",
    "Stormy Sea": "Mar tempestuoso",
    "Summer": "Verano",
    "Sunset": "Atardecer",
    "Sunset on the Sea": "Atardecer en el mar",
    "The Chase": "La persecución",
    "The Cottage": "La cabaña",
    "The Dance": "La danza",
    "The Fisherman": "El pescador",
    "The Forest": "El bosque",
    "The Harbor": "El puerto",
    "The Hunter": "El cazador",
    "The Laborer": "El obrero",
    "The Lake": "El lago",
    "The Market": "El mercado",
    "The Mill": "El molino",
    "The Mountains": "Las montañas",
    "The Old House": "La casa vieja",
    "The Pond": "El estanque",
    "The Port": "El puerto",
    "The Race": "La carrera",
    "The Reader": "La lectora",
    "The River": "El río",
    "The Road": "El camino",
    "The Sea": "El mar",
    "The Shepherd": "El pastor",
    "The Shore": "La orilla",
    "The Sleeper": "La durmiente",
    "The Tower": "La torre",
    "The Valley": "El valle",
    "The Village": "El pueblo",
    "The Waterfall": "La cascada",
    "The Wind": "El viento",
    "Trees": "Árboles",
    "Two Children": "Dos niños",
    "Two Women": "Dos mujeres",
    "Under the Trees": "Bajo los árboles",
    "Vase of Flowers": "Jarrón de flores",
    "Vase with Flowers": "Jarrón con flores",
    "Village": "Pueblo",
    "Village Street": "Calle de pueblo",
    "Waterfall": "Cascada",
    "Waves": "Olas",
    "Wild Flowers": "Flores silvestres",
    "Winter": "Invierno",
    "Winter Landscape": "Paisaje invernal",
    "Woman": "Mujer",
    "Woman with Fan": "Mujer con abanico",
    "Woman with Flowers": "Mujer con flores",
    "Wooded Landscape": "Paisaje arbolado",
    "Woods": "Bosque",
    "Young Girl": "Niña joven",
    "Young Woman Reading": "Mujer joven leyendo",
    "Young Woman Seated": "Mujer joven sentada",
    "Young Woman Standing": "Mujer joven de pie",
    # Religious
    "Baptism of Christ": "Bautismo de Cristo",
    "Christ": "Cristo",
    "Christ and the Woman Taken in Adultery": "Cristo y la mujer sorprendida en adulterio",
    "Christ in the Garden": "Cristo en el jardín",
    "Christ on the Cross": "Cristo en la Cruz",
    "Christ with Crown of Thorns": "Cristo con corona de espinas",
    "Descent from the Cross": "Descendimiento de la Cruz",
    "Holy Family": "Sagrada Familia",
    "Lamentation over the Dead Christ": "Lamentación sobre el Cristo muerto",
    "Madonna": "Madonna",
    "Madonna and Child": "Virgen con el Niño",
    "Nativity": "Natividad",
    "Pietà": "Piedad",
    "Resurrection": "La Resurrección",
    "Saint Anthony": "San Antonio",
    "Saint Catherine": "Santa Catalina",
    "Saint Francis": "San Francisco",
    "Saint Jerome": "San Jerónimo",
    "Saint Joseph": "San José",
    "Saint Luke": "San Lucas",
    "Saint Mary Magdalene": "Santa María Magdalena",
    "Saint Matthew": "San Mateo",
    "Saint Michael": "San Miguel",
    "Saint Nicholas": "San Nicolás",
    "Saint Paul": "San Pablo",
    "Saint Peter": "San Pedro",
    "Saint Stephen": "San Esteban",
    "Saint Thomas": "Santo Tomás",
    "The Baptism of Christ": "El Bautismo de Cristo",
    "The Flight into Egypt": "La Huida a Egipto",
    "The Last Supper": "La Última Cena",
    "The Resurrection": "La Resurrección",
    "The Transfiguration": "La Transfiguración",
    "The Trinity": "La Trinidad",
    "The Virgin": "La Virgen",
    "Virgin": "Virgen",
    # Mythological
    "Bacchus": "Baco",
    "Diana": "Diana",
    "Diana and Her Nymphs": "Diana y sus ninfas",
    "Hercules": "Hércules",
    "Jupiter and Io": "Júpiter e Ío",
    "Leda and the Swan": "Leda y el cisne",
    "Mars and Venus": "Marte y Venus",
    "Mercury": "Mercurio",
    "Minerva": "Minerva",
    "Neptune": "Neptuno",
    "Orpheus": "Orfeo",
    "Perseus": "Perseo",
    "Prometheus": "Prometeo",
    "Psyche": "Psique",
    "Saturn": "Saturno",
    "Venus": "Venus",
    "Venus and Adonis": "Venus y Adonis",
    "Venus and Cupid": "Venus y Cupido",
    # Specific known titles
    "A Thatched Pavilion at the Foot of Two Old Cedar Trees": "Un pabellón de paja al pie de dos viejos cedros",
    "Acrobats at the Cirque Fernando (Francisca and Angelina Wartenberg)": "Acróbatas en el Cirque Fernando",
    "Are They Thinking about the Grape? (Pensent-ils au raisin?)": "¿Piensan en la uva?",
    "Stoke-by-Nayland": "Stoke-by-Nayland",
    "Aeneas Rescuing Anchises from Burning Troy": "Eneas rescatando a Anquises de la Troya en llamas",
    "Apollo Granting Phaeton Permission to Drive the Chariot of the Sun": "Apolo concediendo permiso a Faetón para conducir el carro del sol",
    "An Alpine Scene": "Una escena alpina",
}

# ---------------------------------------------------------------------------
# Traducción de títulos con reglas de patrones
# ---------------------------------------------------------------------------

# Femeninos: palabras que usan "Santa" en vez de "San"
_SANTAS = {
    "Agnes", "Ana", "Anne", "Barbara", "Bárbara", "Catherine", "Catalina",
    "Cecilia", "Clara", "Dorothy", "Elizabeth", "Isabel", "Helena", "Lucia",
    "Lucy", "Margaret", "Margarita", "Martha", "María Magdalena", "Mary",
    "Mary Magdalene", "Monica", "Ursula", "Úrsula", "Veronica", "Verónica",
    "Agnes of Rome", "Anne of Brittany", "Brigid", "Theresa", "Teresa",
    "Rosalia", "Rosalía", "Agatha",
}


def _saint_prefix(name: str) -> str:
    first_word = name.split()[0] if name else ""
    if first_word in _SANTAS or name in _SANTAS:
        return "Santa "
    return "San "


def _apply_patterns(title: str) -> str | None:
    # Self-Portrait
    if re.match(r'^Self-Portrait$', title, re.I):
        return "Autorretrato"
    m = re.match(r'^Self-Portrait\s+(.+)$', title, re.I)
    if m:
        rest = m.group(1).strip(" ()")
        return f"Autorretrato ({rest})"

    # Portrait of / Portrait Study of
    m = re.match(r'^Portrait (?:Study )?of (.+)$', title)
    if m:
        return f"Retrato de {m.group(1)}"

    # Still Life
    if re.match(r'^Still Life$', title, re.I):
        return "Naturaleza muerta"
    m = re.match(r'^Still Life[:\s—-]+(.+)$', title)
    if m:
        return f"Naturaleza muerta: {m.group(1)}"
    m = re.match(r'^Still Life with (.+)$', title)
    if m:
        return f"Naturaleza muerta con {m.group(1)}"
    m = re.match(r'^Still Life[,.]?\s+(.+)$', title)
    if m:
        return f"Naturaleza muerta: {m.group(1)}"

    # View of
    m = re.match(r'^View of (.+)$', title)
    if m:
        return f"Vista de {m.group(1)}"

    # Landscape with / Landscape at / Landscape near
    if re.match(r'^Landscape$', title, re.I):
        return "Paisaje"
    m = re.match(r'^Landscape with (.+)$', title)
    if m:
        return f"Paisaje con {m.group(1)}"
    m = re.match(r'^Landscape at (.+)$', title)
    if m:
        return f"Paisaje en {m.group(1)}"
    m = re.match(r'^Landscape near (.+)$', title)
    if m:
        return f"Paisaje cerca de {m.group(1)}"
    m = re.match(r'^Landscape(?:,|\.)\s+(.+)$', title)
    if m:
        return f"Paisaje: {m.group(1)}"

    # Study of / Study for
    m = re.match(r'^Study of (.+)$', title)
    if m:
        return f"Estudio de {m.group(1)}"
    m = re.match(r'^Study for (.+)$', title)
    if m:
        return f"Estudio para {m.group(1)}"

    # Head of
    m = re.match(r'^Head of (.+)$', title)
    if m:
        return f"Cabeza de {m.group(1)}"

    # Saint / Saints
    m = re.match(r'^Saint (\w[\w\s]+)$', title)
    if m:
        name = m.group(1).strip()
        return f"{_saint_prefix(name)}{name}"

    # St. (abbreviation)
    m = re.match(r'^St\.\s+(\w[\w\s]+)$', title)
    if m:
        name = m.group(1).strip()
        return f"{_saint_prefix(name)}{name}"

    # Scenes from the Life of Saint
    m = re.match(r'^Scenes? from the Life of Saint (.+)$', title)
    if m:
        name = m.group(1).strip()
        return f"Escenas de la vida de {_saint_prefix(name)}{name}"

    # Virgin and Child
    if re.match(r'^Virgin and Child$', title):
        return "Virgen con el Niño"
    m = re.match(r'^Virgin and Child with (.+)$', title)
    if m:
        return f"Virgen con el Niño y {m.group(1)}"
    m = re.match(r'^Virgin and Child,? (.+)$', title)
    if m:
        return f"Virgen con el Niño, {m.group(1)}"

    # Madonna and Child
    if re.match(r'^Madonna and Child$', title):
        return "Virgen con el Niño"
    m = re.match(r'^Madonna and Child with (.+)$', title)
    if m:
        return f"Virgen con el Niño y {m.group(1)}"

    # Annunciation
    if re.match(r'^(?:The )?Annunciation$', title):
        return "La Anunciación"

    # Adoration of the Magi
    if re.match(r'^(?:The )?Adoration of the Magi$', title):
        return "La Adoración de los Reyes Magos"

    # No match
    return None


def traducir_titulo(title: str) -> str:
    if title in TITULOS:
        return TITULOS[title]
    result = _apply_patterns(title)
    if result:
        return result
    return title


# ---------------------------------------------------------------------------
# Limpieza de artista
# ---------------------------------------------------------------------------
_RE_PARENS = re.compile(r'\s*\(.*?\)\s*')
_RE_DATES = re.compile(r',?\s*\d{3,4}[\–\-–—]\d{0,4}')
_RE_BORN = re.compile(r',?\s*(?:born|active|died|b\.|d\.)\s+\d{3,4}', re.I)
_RE_NEWLINE = re.compile(r'\n.*', re.DOTALL)


_RE_ATTRIBUTION = re.compile(
    r'^(?:Attributed to|Workshop of|Circle of|Follower of|School of|After|'
    r'Studio of|Style of|Manner of|Copy after|Copyist after)\s+',
    re.I,
)


def limpiar_artista(artist_display: str) -> str:
    if not artist_display:
        return "Artista desconocido"
    name = _RE_NEWLINE.sub('', artist_display).strip()
    name = _RE_PARENS.sub(' ', name).strip()
    name = _RE_DATES.sub('', name).strip()
    name = _RE_BORN.sub('', name).strip()
    name = _RE_ATTRIBUTION.sub('', name).strip()
    name = re.sub(r',?\s*(?:attributed|workshop|circle|follower|school)\s*$', '', name, flags=re.I).strip()
    name = name.strip(',').strip()
    name = re.sub(r'\s+', ' ', name)
    if not name or name.lower() in ('unknown', 'artist unknown', 'unidentified artist'):
        return "Artista desconocido"
    return name


# ---------------------------------------------------------------------------
# Movimiento
# ---------------------------------------------------------------------------

def traducir_movimiento(style_title: str | None, department_title: str | None) -> str:
    if style_title:
        key = style_title.strip()
        if key in MOVIMIENTOS:
            return MOVIMIENTOS[key]
        key_lower = key.lower()
        for k, v in MOVIMIENTOS.items():
            if k.lower() == key_lower:
                return v
    if department_title:
        key = department_title.strip()
        if key in DEPARTAMENTOS:
            return DEPARTAMENTOS[key]
    return "Arte Europeo"


# ---------------------------------------------------------------------------
# Tipo (medium)
# ---------------------------------------------------------------------------

def traducir_tipo(medium_display: str | None) -> str:
    if not medium_display:
        return "Técnica mixta"
    base = medium_display.split(";")[0].strip()
    if base in TIPOS:
        return TIPOS[base]
    # Fuzzy: check lowercase
    base_lower = base.lower()
    for k, v in TIPOS.items():
        if k.lower() == base_lower:
            return v
    # Partial matches
    if "oil on canvas" in base_lower:
        return "Óleo sobre lienzo"
    if "oil on panel" in base_lower or "oil on wood" in base_lower:
        return "Óleo sobre tabla"
    if "oil on" in base_lower:
        return "Óleo"
    if "tempera" in base_lower:
        return "Témpera"
    if "watercolor" in base_lower or "water-color" in base_lower:
        return "Acuarela"
    if "gouache" in base_lower:
        return "Gouache"
    if "ink" in base_lower:
        return "Tinta"
    if "fresco" in base_lower:
        return "Fresco"
    if "pastel" in base_lower:
        return "Pastel"
    if "charcoal" in base_lower:
        return "Carboncillo"
    if "pencil" in base_lower:
        return "Lápiz"
    if "scroll" in base_lower:
        return "Rollo"
    if "screen" in base_lower:
        return "Biombo"
    if "album" in base_lower:
        return "Álbum"
    return base


# ---------------------------------------------------------------------------
# Época
# ---------------------------------------------------------------------------

def calcular_epoca(anio: int | None) -> str:
    if not anio:
        return "Desconocida"
    if anio < 1200:
        return "Arte Antiguo y Medieval"
    if anio < 1400:
        return "Medieval"
    if anio < 1600:
        return "Renacimiento"
    if anio < 1700:
        return "Barroco"
    if anio < 1800:
        return "Siglo XVIII"
    if anio < 1850:
        return "Romanticismo"
    if anio < 1900:
        return "Siglo XIX"
    if anio < 1945:
        return "Primer Siglo XX"
    return "Arte Contemporáneo"


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def slugify(texto: str) -> str:
    texto = texto.lower().strip()
    texto = re.sub(r'[áàä]', 'a', texto)
    texto = re.sub(r'[éèë]', 'e', texto)
    texto = re.sub(r'[íìï]', 'i', texto)
    texto = re.sub(r'[óòö]', 'o', texto)
    texto = re.sub(r'[úùü]', 'u', texto)
    texto = re.sub(r'[ñ]', 'n', texto)
    texto = re.sub(r'[^\w\s-]', '', texto)
    texto = re.sub(r'[\s_-]+', '-', texto)
    return texto[:60].strip('-')


def es_valida(obra: dict) -> bool:
    return bool(
        obra.get("image_id")
        and obra.get("is_public_domain")
        and obra.get("artwork_type_title") == "Painting"
        and obra.get("title")
        and limpiar_artista(obra.get("artist_display", "")) != "Artista desconocido"
    )


def normalizar(obra: dict) -> dict:
    titulo_original = obra.get("title", "Sin título")
    titulo = traducir_titulo(titulo_original)
    artista = limpiar_artista(obra.get("artist_display", ""))
    anio = obra.get("date_end") or None
    movimiento = traducir_movimiento(obra.get("style_title"), obra.get("department_title"))
    tipo = traducir_tipo(obra.get("medium_display"))
    epoca = calcular_epoca(anio)
    image_id = obra["image_id"]

    return {
        "id": slugify(f"{titulo}-{artista}"),
        "titulo": titulo,
        "titulo_original": titulo_original,
        "artista": artista,
        "anio": anio or 0,
        "anio_display": obra.get("date_display", ""),
        "movimiento": movimiento,
        "tipo": tipo,
        "epoca": epoca,
        "museo": "Art Institute of Chicago",
        "image_url": ARTIC_IMAGE.format(image_id=image_id),
    }


# ---------------------------------------------------------------------------
# Descarga desde ARTIC
# ---------------------------------------------------------------------------

def descargar_raw() -> list[dict]:
    print("Descargando IDs de pinturas de dominio público del ARTIC...")
    all_ids: list[int] = []
    min_id = 0

    with tqdm(desc="IDs", unit="batch") as pbar:
        while True:
            filtros = [
                {"term": {"is_public_domain": True}},
                {"term": {"artwork_type_title.keyword": "Painting"}},
                {"exists": {"field": "image_id"}},
            ]
            if min_id > 0:
                filtros.append({"range": {"id": {"gt": min_id}}})

            payload = {
                "query": {"bool": {"filter": filtros}},
                "sort": [{"id": {"order": "asc"}}],
                "_source": ["id"],
                "size": 100,
            }
            try:
                r = requests.post(
                    f"{ARTIC_API}/artworks/search",
                    json=payload,
                    headers=HEADERS,
                    timeout=30,
                )
                r.raise_for_status()
            except Exception as e:
                print(f"\nError buscando IDs: {e}")
                time.sleep(2)
                continue

            data = r.json()
            hits = [h["_source"]["id"] for h in data.get("data", [])]
            if not hits:
                break
            all_ids.extend(hits)
            min_id = max(hits)
            pbar.update(1)
            time.sleep(0.15)

    print(f"IDs encontrados: {len(all_ids)}")

    # Descargar detalles en lotes de 100
    print("Descargando detalles...")
    raw: list[dict] = []
    for i in tqdm(range(0, len(all_ids), 100), unit="lote"):
        chunk = all_ids[i: i + 100]
        try:
            r = requests.get(
                f"{ARTIC_API}/artworks",
                params={"ids": ",".join(str(x) for x in chunk), "fields": FIELDS, "limit": 100},
                headers=HEADERS,
                timeout=30,
            )
            r.raise_for_status()
            raw.extend(r.json().get("data", []))
        except Exception as e:
            print(f"\nError en lote {i}: {e}")
        time.sleep(0.15)

    return raw


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(solo_procesar: bool = False):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Cargar o descargar datos crudos
    if solo_procesar or RAW_PATH.exists():
        print(f"Cargando datos crudos desde {RAW_PATH}...")
        with open(RAW_PATH, encoding="utf-8") as f:
            raw_data = json.load(f)
        raw = raw_data if isinstance(raw_data, list) else raw_data.get("paintings", raw_data.get("data", []))
    else:
        raw = descargar_raw()
        with open(RAW_PATH, "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False, indent=2)
        print(f"Datos crudos guardados en {RAW_PATH}")

    print(f"Procesando {len(raw)} obras...")

    paintings: list[dict] = []
    ids_vistos: set[str] = set()
    sin_traducir = 0

    for obra in tqdm(raw, unit="obra"):
        if not es_valida(obra):
            continue
        p = normalizar(obra)
        # Evitar IDs duplicados
        base_id = p["id"]
        uid = base_id
        counter = 2
        while uid in ids_vistos:
            uid = f"{base_id}-{counter}"
            counter += 1
        p["id"] = uid
        ids_vistos.add(uid)

        if p["titulo"] == p["titulo_original"]:
            sin_traducir += 1

        paintings.append(p)

    datos = {
        "paintings": paintings,
        "total": len(paintings),
        "fuente": "Art Institute of Chicago",
    }
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)

    traducidos = len(paintings) - sin_traducir
    print(f"\nGuardados {len(paintings)} cuadros en {OUTPUT_PATH}")
    print(f"Titulos traducidos: {traducidos}/{len(paintings)} ({100*traducidos//len(paintings)}%)")
    if paintings:
        p = paintings[0]
        print(f"Ejemplo: {p['titulo']} ({p['titulo_original']}) — {p['artista']} ({p['anio_display']})")
        print(f"         Movimiento: {p['movimiento']} | Tipo: {p['tipo']} | Época: {p['epoca']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Genera paintings.json desde el ARTIC")
    parser.add_argument(
        "--solo-procesar",
        action="store_true",
        help="No descarga: usa _raw.json existente",
    )
    args = parser.parse_args()
    main(solo_procesar=args.solo_procesar)
