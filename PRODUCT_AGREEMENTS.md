# ToDo — اتفاقات الواجهة والعمل

مرجع العمل: فيديو Séquence 02_2.mp4 (4:51)، وصور المستخدم، واتفاقات المحادثة.
هذه متطلبات التنفيذ؛ وجودها هنا لا يعني أن الميزة مكتملة أو مجربة.

## قواعد مؤكدة
- البيع يستمر عندما يكون مخزون المنتوج المسجل صفراً أو سالباً، بدون نافذة تعطل البيع. كل بيع يسجل حركة مخزون.
- الباركود غير المعروف: نافذة حمراء كبيرة، الباركود ظاهر، صوت قصير، إضافة منتوج بالباركود المعبأ أو العودة للسكان، مع حفظ السلة.
- تعديل المخزون مباشرة من بطاقة المنتوج؛ الحركة تتسجل تلقائياً والملاحظة اختيارية.
- منتوجات بدون باركود مسموحة وتباع بالصور أو البحث.

## مسار الفيديو المطلوب
- التيكي يساراً، صور كبيرة مع الاسم والثمن يميناً، والعائلات سهلة الاختيار.
- الباركود والكمية في الأعلى؛ المجموع والدفع ثابتان وظاهران.
- السكان المتكرر يزيد كمية نفس السطر؛ الضغط على كامل بطاقة الصورة يضيف المنتوج.
- كتابة الكمية مباشرة مع دعم الكيبورد؛ لا حاجة لتكرار الضغط على +.
- Fonctions: Duplicata، Remise، تعديل الثمن والكمية، Attente، Liste d'attente.
- بطاقة منتوج مختصرة: الاسم، باركود اختياري، صورة، شراء وبيع، مخزون وتنبيه، عائلة بقائمة و+.
- إضافة عائلة من البطاقة تجعلها متاحة فوراً في الاختيارات.
- العروض بخانات: حد كمية وثمن وحدة، أو كمية مجموعة وثمن المجموعة، مع توضيح التطبيق.
- خلاص نقداً/بطاقة، المدفوع والصرف بأرقام كبيرة، اختصارات أوراق نقدية وخيار طباعة.
- بعد الخلاص السلة جاهزة للعملية التالية مع بقاء ملخص آخر عملية.

## التحقق قبل وصف النسخة بالجاهزة
- تجربة فعلية للواجهة على Windows: سكان، صور، كمية، انتظار واسترجاع، تخفيض، خلاص، طباعة/نسخة التيكي.
- اختبار صفر/سالب المخزون، الباركود غير المعروف، وحفظ السلة بعد إغلاق النوافذ.
- اختبار العائلة الجديدة والمنتوج بلا باركود والعروض بأمثلة مالية واضحة.
- إرفاق نسخة Windows قابلة للتنزيل؛ لا اعتبار ملف المصدر نسخة Windows.

## خريطة الصفحات — مطابقة للصور
- الصفحة الرئيسية: ستة مداخل فقط: Vente، Stock، Journal، Gestion، Paramètres، Statistiques.
- Vente: التيكي في اليسار؛ CODE BARRE وDESIGNATION والكمية ولوحة الأرقام فوق؛ عائلات ثابتة على اليسار؛ Liste Article وListe Photos؛ الصور فقط للمنتوجات التي عندها صورة؛ Fonctions وSOLDER مع/بدون طباعة.
- Articles: جدول Code، Article، Famille، PRIX A، PRIX V، Stock، إجراءات؛ بطاقة Nouveau بنفس Code/Article/Famille/Prix Achat/Prix Vente/Stock/Alert/Prix MP/Image/PRIX QTE/QTE MIN؛ مؤشرات Articles وPromotions وPrix QTE وقيم المخزون.
- Stock: الكمية، الإنذارات، الحركات، الجرد والسجل؛ ماشي بطاقة تعريف المنتوج.
- Journal: رقم التيكي، التاريخ، الوقت، المقال، الثمن، الكمية، التخفيض، الصافي، الكاشير، البائع، الزبون، العملية؛ فترة من/إلى، أنواع التقرير، consulter/imprimer/export.
- Gestion: Réceptions، Sorties، Inventaire، Mouvements de Stock، Fournisseurs، Règlements، État Crédits، Clients، Dépenses، Rendez-vous.
- Statistiques: Evolution des ventes، Top 10 Articles، Top Clients/Caissier، Evolution Article، الفترة، Total Ventes، Tickets، Retours.
- Paramètres: المحل، العملة، الضرائب، التيكي، الباركود، المستخدمين، النسخ الاحتياطي، شاشة الزبون، الطابعة، السكان، الاختصارات واللغة.

أي صفحة أو زر ما داخلش فهاد الخريطة أو ما باينش فالفيديو/الصور ما كيدخلش فواجهة النسخة المقبلة.

## Fonctions — précisions confirmées le 20/09/2026
- Divers : l'utilisateur confirme « produit non enregistré ou montant supplémentaire ». Saisie libellé/prix/quantité ; ligne distincte sur le ticket, sans mouvement de stock. Vente, attente/reprise et retour testés.
- Flash : l'utilisateur ne connaît pas son rôle ; aucune fonction arbitraire ne lui est attribuée.
- Alerte : le comportement de la fenêtre reste à préciser.
- Calculatrice : calcul décimal local, sans modification du ticket.
- Lock : garde le ticket et exige le PIN du caissier actif ; verrouille les changements de page et la fermeture normale.
- Validation locale : 34 tests métier ; parcours Tk incluant Divers, calculatrice, PIN erroné/correct et conservation du panier.
- Thème : accents Bleu/Vert/Violet enregistrés. Tiroir : commande ESC/POS configurable, matériel physique non testé.
- Reste : rôle de Flash/Alerte, revue complète de l'exécutable et impression physique.

## Fournisseurs et navigation Gestion — 20/09/2026
- Fournisseurs ouvre une vraie liste avec création/modification (nom, téléphone, notes) et historique des réceptions.
- Réceptions : choix d'un fournisseur existant ou création par +, sélection immédiate ; les factures restent liées à son identifiant après renommage.
- Suppression du groupe fournisseurs en double. Clients/règlements/crédits ne redirigent plus vers des pages sans rapport : statut « à compléter » explicite.
- Sorties, Inventaire dédié, clients, règlements, crédits et Rendez-vous restent à implémenter ; la présence des entrées ne signifie pas achèvement.
- Validation locale : 39 tests métier ; parcours Tk à 1100×640 avec création fournisseur, réception liée, renommage, historique, vente et reçu PDF.
