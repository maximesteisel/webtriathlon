Intro
=====

Webtriathlon est un programme permettant de
gérer une course comportant plusieurs étapes.

Webtriathlon se base sur un serveur central
qui calcule le classement, grâce aux informations
que lui envoie le ou les encodeurs, éventuellement
sur des ordinateurs différents. Les résultats sont
publiés en temps réel via le web, et peuvent donc
être consultés depuis n'importe quel ordinateur connecté 
au serveur (voire via internet).

Mise en place
=============

0. Mise en réseau (optionnel)
-----------------------------

Si vous comptez utiliser plusieurs ordinateurs, 
il est nécessaire de les connecter via un réseau local ou via internet.
Assurez vous que le/les serveurs possède une adresse fixe connue. Par exemple,
pour un réseau local, vous pouvez utiliser 192.168.1.5 (évitez 192.168.1.1 ou 
192.168.1.254 qui sont souvent utilisés par les routeurs)

1. Installation des dépendances
-------------------------------

Webtriathlon repose sur un certain nombre de programme et librairie 
open-source, notamment python, gtk (pour l'affichage de fenêtre), Django (pour la
génération du HTML), Twisted (pour le serveur proprement dit), etc.

Les librairie écrite en python (Twisted, Django, ...) sont directement incluses 
dans le programme, les autres nécéssitent d'être installées.

Windows
*******

Lancez les installateurs contenu dans le dossier "installers", de préférence
dans l'ordre. Un redémarrage est conseillé ensuite.

Linux
*****

Installez les paquets python2.6, libgtk2, python-gtk2, mysql, et python-mysqldb.

2. Configuration du serveur
--------------------------

Pour lancer le serveur, cliquez sur le fichier server.py. Une fenetre
s'ouvre et peut vous demander quelques informations, notamment pour creer un
compte utilisateur la première fois.
L'ip du serveur peut être trouvé en exécutant la commande ipconfig dans 
un terminal sous windows ou ifconfig sur linux
    
3. Configuration des encodeurs
-----------------------------

Lancez le programme en cliquant sur le fichier encoder.py 
puis indiquez l'adresse ip de l'ordinateur serveur, qui est
127.0.0.1 si le serveur est sur la même machine,
le port (qui devrait toujours être 8000) et le nom du poste de pointage. 

L'encodeur peut fonctionner en mode déconnecté, et donc il n'est pas nécessaire
qu'il soit connecté au serveur. Bien sur, s'il n'est pas connecté, les résultats ne sont
pas en temps réel sur le serveur. Les résultat sont enregistrés sur un fichier,
qui doit être envoyé au serveur via le site d'administration (voir plus loin).
Le passage du mode connecté au mode déconnecté et inversément se fait automatiquement
selon que le client arrive ou non à se connecter au serveur.

4. Configuration des écrans d'affichage
---------------------------------------

Sur ces ordinateurs, ouvrez le navigateur internet et entrer l'adresse ip du serveur
suivie du port dans la barre d'adresse. (p. e. http://192.168.1.1:8000).

Il n'est pas nécessaire d'installer webtriathlon sur ces ordinateurs. Un navigateur suffit.

Administration d'avant-course
=============================

L'admistration se fait via la partie administration du site des résultats.

Un certain nombre de paramètres doivent être introduits avant de commencer la course.
    
1. Les *types de courses*
-------------------------

Par exemple natation, vélo, ... ils sont caractérisés par une *vitesse maximale*, qui permet de
détecter les éventuels tricheurs, une *vitesse moyenne*, qui est utilisée dans les classements pendant
la course, pour comparer des équipes qui sont dans des étapes différentes de la course et 
une *vitesse minimale* qui permet de détecter un oubli d'encodage.

2. Les *catégories*
-------------------

Chaque équipe est classée dans une catégorie. Deux équipes peuvent être classées dans la même
catégorie même si elles concourent à des endroits ou des moments différents, et même si elles
ont des parcours differents. Les détails du déroulement
de la course sont encodés dans l'object Parcours, qui est attribué à chaque équipe.
Les équipes sont classés sur base d'un temps corrigé. Ce temps correspond au temps
qu'aurait fait une équipe, sur base de ses moyennes, si elle avait fait un parcours
de référence. Le parcours de référence est le premier parcours encodé dans la catégorie.

Si une équipe suit ce parcours, alors son temps corrigé est le même que son temps réel.
Si une équipe fait par exemple un tour en trop, son temps corrigé sera plus petit que
son temps réel. Si une équipe suit un parcours alternatif légérement plus court
que le parcours de référence, son temps sera corrigé à la hausse, proportionellement
à la différence de longueur. 

3. Les *sous-catégories*
------------------------

Permettent de regrouper certaines équipes, par exemple par age, ou
bien en fonction des règles de relais, de façon à pouvoir établir
un classement séparé en plus du classement général.

4. Les *parcours* et jonctions
------------------------------

Décrivent le nombre et la longueur des tours et l'endroit de pointage pour chaque étapes

Si 2 étapes successives sont encodées à des endroits différents,
il est nécessaire de définir une jonction entre les deux. Le paramètre 
*poste* de la jonction est soit le début de la jonction
(si la jonction est avant une étape) soit la fin (si elle est après).
Par exemple, si l'étape 1 [en vélo] est encodé au poste A et l'étape 2 [à pied] au poste B,
alors il faudra soit un jonction après 1 (avec B renseigné comme poste), soit avant 2
(avec A renseigné comme poste). Notez que ce n'est pas équivalent: la première possibilité
implique que la jonction se fait en vélo tandis que la deuxième implique
qu'elle est se fait à pied. Il est aussi possible qu'il y ait à la fois une jonction après
l'étape 1 et avant l'étape 2, auquel cas, il faut qu'il y ait un troisième poste (C) à l'endroit 
de transition. Dans ce cas, les deux jonctions renseignent C comme poste.

Une longueur de 0 indique que la jonction ne fait pas partie de la course. Le temps que passent les
équipe pendant cette jonction sera ignoré pour le classement.

5. Les *équipes*
----------------


Pour chaque équipe, il faut remplir au minimum les paramètre *Numéro* (numéro d'équipe),
*Catégorie* et *Parcours*. Il peut être utile de mentionner les *membres* et les *sous-catégories*  

Une fois la course commencée, changer la catégorie ou le parcours d'une équipe est déconseillé.
Si vous le faites, il faut ensuite aligner les passages de l'équipe (via le lien rouge sur la page de l'équipe)
de manière à ce que les passages soit attribués au bonnes étapes. Si vous aviez fait des
changements manuels (par exemple pour indiquer que l'équipe avait fait un tour en
trop quelque part), il vous faudra recommencer.



Encodage
========

L'encodage fonctionne selon deux mode: connecté ou non-connecté. Il passe
de l'un à l'autre automatiquement si il perd la connexion avec le serveur. En mode non-connecté, les pointages sont
enregistrés dans un fichier ('nom_du_poste.psave').

La fenêtre principale est divisée en trois partie: la liste des pointage effectués; 
une partie pour pointer une équipe, et une partie pour pointer toutes les équipes d'un
même parcours.

Pour pointer une équipe, il faut saisir son numéro dans la zone de saisie, puis appuyer sur Enter ou cliquer
sur "Pointer l'équipe". Ensuite, on peut immédiatement saisir un autre numéro sans devoir cliquer
sur la zone de saisie.

En mode connecté, après avoir effectuer un pointage, le serveur devine l'étape dans lequel se trouve l'équipe quand
il est passé. Il arrive que le programme se trompe, en conséquence généralement d'une erreur précédente de l'opérateur ou 
de l'équipe. Dans ce cas, il est possible de modifier cette valeur en cliquant dessus dans la liste des pointage,
puis en entrant l'étape réelle. Il est aussi possible de modifier l'équipe, si on s'est trompé en encodant.

L'encodeur affiche aussi dix bouttons numérotés, correspondant aux équipe qui selon
le serveur ont le plus de chance de passer bientôt. On peut pointer l'équipe
en cliquant sur le boutton ou en l'encodant normalement.

Si on encode une équipe qui n'existe pas dans le serveur, le pointage est enregistré dans un fichier comme
si l'encodeur était déconnecté. Cela permet de créer l'équipe après coup et d'avoir tout ses pointages.
Il est possible de creer une équipe ensuite, soit directement via l'encodeur, soit
via le site d'administration. De même, il y a un boutton pour re-envoyer tout les pointage
sauvegardés, ou on peut envoyer le fichier de sauvegarde via le site d'administration.

L'encodeur peut aussi permettre de pointer toute les équipe d'un même parcours, ce qui est principalement
utile pour les départs groupés. Le site d'administration possède une fonctionnalité similaire pour 
ajouter des passages à une catégorie, un parcours et/ou une sous-catégorie après-coup.

Administration pendant la course
================================

Pendant la course, il est possible d'utiliser l'administration
pour ajouter ou supprimer des équipes, ajouter, modifier ou supprimer
des passage et changer des paramètres informatifs (p.e. changer
une sous-catégorie ou le nom d'un membre, etc.). Celà se fait
pricipalement sur le site d'administration. La base de donnée
peut être modifié via ce site d'administration. L'onglet "outils"
contient différentes fonctions qui permettent de faire des modifications sur
un grand nombre d'objects à la fois.

Il faut garder à l'esprit plusieurs point importants:

Si l'on supprime un passage, les tours avant et après le passage
sont fusionnés. Il n'est pas possible de supprimer un tour de façon à avoir
un "trou" dans la course, par exemple au cas ou une équipe aurait fait un tour
de trop (mais la méthode de classement permet de limiter le désavantage)

Il est déconseillé de modifier les paramètres d'une catégorie ou d'un parcours
une fois la course commencée. Si ces paramètres sont modifiés, le serveur mettra
un certain temps à mettre à jour les classements pour en tenir compte. Cela peut 
être acceléré grâce à la fonction "tout recalculer" dans le site d'administration,
mais cela rends le serveur quasiment inutilisable quelque minutes 
donc il vaut mieux le faire après la fin de la course.

Pour ajouter un passage, la méthode la plus simple consiste à se rendre
sur la page d'administration de l'équipe, et de descendre en dessous de
la liste des passages. Trois passages sont laissés vide et peuvent être 
remplis. Si il faut rajouter plus de trois passage, remplissez les trois
premier puis cliquez sur 'Enregistrer et continuer les modification' 
pour que trois nouveau passages vide apparaissent.


Administration après-course
===========================

Après la course, il est bien sur possible d'effectuer toute les actions 
possible pendant la course (le programme ne sait d'ailleurs pas quand
la course se finit).

Plusieurs fonctions utiles pour cette phase se trouvent dans l'onglet 
outils de l'administration.

La plus utile est la liste des erreurs à corriger. Toute les anomalies
détectées par le programme y sont listé, parfois avec une proposition
de réparation automatique.

Vous trouverez aussi dans cet onglet un lien vers les versions imprimables
du classement et des feuilles de courses.

Pensez aussi à consulter le lien feedback qui permet de voir les
commentaires des visiteurs, et qui peut contenir des messages
signalant des erreurs dans l'encodage des résultats.

Il est possible de faire une sauvegarde partielle (p.e. seulement sauvegarder
les catégories et parcours) ou une sauvegarde totale.

Lorsque vous chargez une sauvegarde, rien n'est supprimé de votre base de donnée,
si l'objet qui se trouve dans la sauvegarde existe aussi dans votre base de donnée
(sur base de sa clé primaire, un numéro attribué automatiquement à chaque object),
il sera modifié, sinon il sera ajouté. Dans le cas des passages, la clé primaire
est un uuid (universaly unique identifier), ce qui garanti que deux passages différents
n'auront jamais le même identifiant.

Si vous voulez remplacer la base de donnée par la sauvegarde, il faut remettre la base à
blanc d'abords (pour ce faire, suivez le lien "tout supprimer" ou "supprimer tout les passages").

Si vous constatez, avant d'imprimer le classement, qu'il y a des erreurs dans
les temps corrigés, les tours ou le classement lui-même, il est recommandé
d'utiliser l'outil "tout recalculer". C'est notamment nécéssaire lorsque
l'on change les paramètres du parcours pendant la course

Méthode de classement
=====================

La méthode de classement utilisée par le programme est un peu compliquée pour
permettre à différentes équipes ayant des parcours différents d'être comparées de
la manière la plus juste possible et en temps réel.
Le programme s'accommode aussi des éventuels tours
manquants ou des tours en trop d'une équipe. Il est bien entendu possible 
de disqualifier une équipe si elle ne suit pas le parcours officiel, mais ce n'est pas automatique.

Le classement se fait sur base d'un 'temps projeté' qui permet d'avoir une estimation
du temps totale d'une équipe si elle avait fait le parcours officiel. Ce temps projeté peut
être calculé à n'importe quel moment de la course, ce qui permet de faire les classements provisoires.

Ce temps projeté est égal à la somme des temps projeté pour chaque étape, qui est égal à la vitesse moyenne 
dans cette étape multiplié par la longueur totale (officiele) de l'étape.

Les jonctions et les tours supplémentaire contribuent à la moyenne de vitesse de l'étape
mais pas à la longueur totale "officielle", il n'handicapent donc pas l'équipe, excepté bien
sur si ce(s) tours supplémentaire était plus lent que les autres.

Pendant la course, si une équipe n'a pas encore commencé une étape, ou que les données
ne sont pas encore disponibles (encodeur en mode non-connecté), 
la vitesse moyenne utilisée est celle mentionnée dans le type de tours. 
Le réalisme de ce paramètre a donc une grande influence
sur l'exactitude des classement provisoires en début de course, 
en particulier si toutes les équipes ne partent pas en même temps.

Compatibilité
=============

Ce programme est écrit en python, version 2.5 (www.python.org).

La partie serveur est basée sur le framework Django (www.djangoproject.com), version 1.1,
et la bibliotheque twisted (www.twistedmatrix.com), version 10.0
la partie encodeur est basée sur la bibliothèque graphique GTK+ (www.gtk.org) , version 2
en utilisant les binding python fournis par le projet pygtk (www.pygtk.org)

Webtriathlon est testé sur Ubuntu/Linux. Il est en principe compatible Windows,
à condition d'installer toutes les dépendances. 
