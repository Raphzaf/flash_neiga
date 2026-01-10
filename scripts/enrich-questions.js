#!/usr/bin/env node

/**
 * Script d'enrichissement des questions
 * 
 * Ce script enrichit data_v3.json avec les URLs d'images extraites 
 * du champ description4 de sample_questions.json.
 * 
 * Usage: node scripts/enrich-questions.js
 */

const fs = require('fs');
const path = require('path');

// Chemins des fichiers
const DATA_V3_PATH = path.join(__dirname, '../data/data_v3.json');
const SAMPLE_QUESTIONS_PATH = path.join(__dirname, '../data/sample_questions.json');
const OUTPUT_PATH = path.join(__dirname, '../data/data_enriched.json');

// Regex pour extraire les URLs d'images du HTML
const IMG_URL_REGEX = /<img[^>]+src="([^">]+)"/;

/**
 * Extrait l'URL de l'image depuis le champ HTML description4
 * @param {string} description4 - Le contenu HTML du champ description4
 * @returns {string|null} L'URL de l'image ou null si pas d'image
 */
function extractImageUrl(description4) {
  if (!description4) return null;
  
  const match = description4.match(IMG_URL_REGEX);
  return match ? match[1] : null;
}

/**
 * Fonction principale d'enrichissement
 */
function enrichQuestions() {
  console.log('🚀 Démarrage de l\'enrichissement des questions...\n');
  
  // 1. Charger les fichiers JSON
  console.log('📂 Chargement des fichiers...');
  let dataV3, sampleQuestions;
  
  try {
    dataV3 = JSON.parse(fs.readFileSync(DATA_V3_PATH, 'utf8'));
    sampleQuestions = JSON.parse(fs.readFileSync(SAMPLE_QUESTIONS_PATH, 'utf8'));
  } catch (error) {
    console.error('❌ Erreur lors du chargement des fichiers:', error.message);
    process.exit(1);
  }
  
  // Vérifier que les structures sont correctes
  if (!dataV3.questions || !Array.isArray(dataV3.questions)) {
    console.error('❌ Format invalide pour data_v3.json: propriété "questions" manquante ou invalide');
    process.exit(1);
  }
  
  if (!sampleQuestions.items || !Array.isArray(sampleQuestions.items)) {
    console.error('❌ Format invalide pour sample_questions.json: propriété "items" manquante ou invalide');
    process.exit(1);
  }
  
  const questionsV3 = dataV3.questions;
  const sampleItems = sampleQuestions.items;
  
  console.log(`✓ Chargé ${questionsV3.length} questions de data_v3.json`);
  console.log(`✓ Chargé ${sampleItems.length} questions de sample_questions.json\n`);
  
  // 2. Vérifier que les deux fichiers ont le même nombre de questions
  if (questionsV3.length !== sampleItems.length) {
    console.warn(`⚠️  Attention: Nombre de questions différent (${questionsV3.length} vs ${sampleItems.length})`);
  }
  
  // 3. Enrichir les questions
  console.log('🔄 Enrichissement des questions en cours...');
  let withImages = 0;
  let withoutImages = 0;
  
  const enrichedQuestions = questionsV3.map((question, index) => {
    const sampleItem = sampleItems[index];
    
    if (!sampleItem) {
      console.warn(`⚠️  Pas de correspondance pour la question à l'index ${index}`);
      return {
        ...question,
        imageUrl: null,
        questionId: null,
        index: null
      };
    }
    
    // Extraire l'URL de l'image
    const imageUrl = extractImageUrl(sampleItem.raw?.description4);
    
    if (imageUrl) {
      withImages++;
    } else {
      withoutImages++;
    }
    
    // Créer la question enrichie
    return {
      ...question,
      imageUrl: imageUrl,
      questionId: sampleItem.raw?._id || null,
      index: sampleItem.index || null
    };
  });
  
  // 4. Créer le fichier de sortie
  const enrichedData = {
    questions: enrichedQuestions
  };
  
  console.log('✓ Enrichissement terminé\n');
  
  // 5. Sauvegarder le fichier enrichi
  console.log('💾 Sauvegarde du fichier enrichi...');
  try {
    fs.writeFileSync(OUTPUT_PATH, JSON.stringify(enrichedData, null, 2), 'utf8');
    console.log(`✓ Fichier sauvegardé: ${OUTPUT_PATH}\n`);
  } catch (error) {
    console.error('❌ Erreur lors de la sauvegarde:', error.message);
    process.exit(1);
  }
  
  // 6. Afficher les statistiques
  console.log('📊 Statistiques:');
  console.log('─'.repeat(50));
  console.log(`Total de questions:        ${enrichedQuestions.length}`);
  console.log(`Questions avec images:     ${withImages} (${Math.round(withImages / enrichedQuestions.length * 100)}%)`);
  console.log(`Questions sans images:     ${withoutImages} (${Math.round(withoutImages / enrichedQuestions.length * 100)}%)`);
  console.log('─'.repeat(50));
  console.log('\n✅ Enrichissement terminé avec succès!');
}

// Exécuter le script
if (require.main === module) {
  enrichQuestions();
}

module.exports = { enrichQuestions, extractImageUrl };
