-- Migration 005: nombres de cursos en inglés
-- Target DB : gestion_facturas_amicana
-- Run once  : mysql -u root -p gestion_facturas_amicana < database/migrations/005_curso_nombres_ingles.sql
--
-- Renombra los cursos seedeados al inglés (es un instituto de idiomas).
-- Solo actualiza los nombres si coinciden con los originales en español;
-- no toca cursos creados por el admin manualmente.

USE gestion_facturas_amicana;

UPDATE cursos SET nombre = 'English A1 - Beginners'
    WHERE nombre = 'Ingles A1 - Principiantes';

UPDATE cursos SET nombre = 'English B1 - Intermediate'
    WHERE nombre = 'Ingles B1 - Intermedio';

UPDATE cursos SET nombre = 'English C1 - Advanced'
    WHERE nombre = 'Ingles C1 - Avanzado';

UPDATE cursos SET nombre = 'Conversation Class'
    WHERE nombre = 'Conversacion Ingles';
