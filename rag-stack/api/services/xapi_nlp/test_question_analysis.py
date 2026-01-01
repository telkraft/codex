# test_question_analysis.py
"""
Soru Analiz Sisteminin Kapsamlı Test ve Kullanım Örnekleri
==========================================================

Bu dosya:
1. Sistemin nasıl çalıştığını gösterir
2. Çeşitli soru tipleri için örnekler sunar
3. Algoritmanın ne kadar başarılı olduğunu test eder
"""

from advanced_intent_router import AdvancedIntentRouter
from canonical_questions import QuestionType
from xapi_statement_schema import XAPI_STATEMENT_SCHEMA, validate_statement


# ============================================================================
# TEST SORULARI
# ============================================================================

TEST_QUESTIONS = [
    
    # Malzeme Kullanım Soruları
    {
        "category": "Malzeme Kullanımı",
        "questions": [
            "2023 yılında hangi malzemeler kullanıldı?",
            "En çok kullanılan 10 malzeme nedir?",
            "MAN otobüslerde hangi parçalar değiştirildi?",
            "Fuchs yağ kullanımı nasıl?",
            "Ocak ayında kullanılan malzemeler",
            "Fren diski kullanım dağılımı",
        ],
        "expected_type": QuestionType.MATERIAL_USAGE,
    },
    
    # Maliyet Soruları
    {
        "category": "Maliyet Analizi",
        "questions": [
            "2023 yılı toplam bakım maliyeti ne kadar?",
            "Hangi araç tipinde daha çok harcama yapıldı?",
            "Aylık ortalama bakım maliyeti nedir?",
            "En yüksek maliyetli işlemler hangileri?",
            "MAN otobüslerin bakım maliyeti",
        ],
        "expected_type": QuestionType.COST_ANALYSIS,
    },
    
    # Bakım Geçmişi Soruları
    {
        "category": "Bakım Geçmişi",
        "questions": [
            "70886 plakalı aracın bakım geçmişi nedir?",
            "Bu araç son ne zaman bakım gördü?",
            "2023'te kaç kere servise geldi?",
            "Araç 71234'ün servis kayıtları",
            "70886 bakım kayıtlarını göster",
        ],
        "expected_type": QuestionType.MAINTENANCE_HISTORY,
    },
    
    # Arıza Soruları
    {
        "category": "Arıza Analizi",
        "questions": [
            "En sık görülen arızalar neler?",
            "WD1A2000000ZW arızası kaç kere oluştu?",
            "MAN otobüslerde hangi arızalar var?",
            "2023 yılında arıza dağılımı nasıl?",
            "En fazla görülen 5 arıza kodu",
        ],
        "expected_type": QuestionType.FAULT_ANALYSIS,
    },
    
    # Araç Bazlı Sorular
    {
        "category": "Araç Bazlı",
        "questions": [
            "Hangi araçlar en çok servise geliyor?",
            "70886 plakalı araç hakkında bilgi",
            "En maliyetli araçlar hangileri?",
            "Araç bazında bakım sayıları",
        ],
        "expected_type": QuestionType.VEHICLE_BASED,
    },
    
    # Müşteri Bazlı Sorular
    {
        "category": "Müşteri Bazlı",
        "questions": [
            "En çok harcama yapan müşteriler kimler?",
            "Müşteri 159485 firma bilgileri",
            "Müşteri bazında işlem sayıları",
            "Hangi müşteriler düzenli geliyor?",
        ],
        "expected_type": QuestionType.CUSTOMER_BASED,
    },
    
    # Servis Bazlı Sorular
    {
        "category": "Servis Bazlı",
        "questions": [
            "Hangi servisler en yoğun?",
            "R540 servisinde ne kadar iş yapıldı?",
            "Servis bazında gelir dağılımı",
            "En çok malzeme hangi serviste kullanıldı?",
        ],
        "expected_type": QuestionType.SERVICE_BASED,
    },
    
    # Zaman Serisi Soruları
    {
        "category": "Zaman Serisi",
        "questions": [
            "Yıllara göre bakım sayıları nasıl değişti?",
            "Aylık malzeme kullanımı trendi",
            "2020-2023 arası maliyet değişimi",
            "Zaman içinde arıza oranı değişimi",
        ],
        "expected_type": QuestionType.TIME_SERIES,
    },
    
    # Mevsimsel Sorular
    {
        "category": "Mevsimsel",
        "questions": [
            "Kış aylarında hangi arızalar artıyor?",
            "Mevsimsel malzeme kullanımı",
            "Yaz ayları bakım maliyeti",
            "Mevsime göre servis yoğunluğu",
        ],
        "expected_type": QuestionType.SEASONAL,
    },
    
    # Karşılaştırma Soruları
    {
        "category": "Karşılaştırma",
        "questions": [
            "MAN ve Mercedes otobüs maliyetlerini karşılaştır",
            "2022 ve 2023 yıllarını karşılaştır",
            "Kış ve yaz ayları arıza oranları",
            "R540 ve R600 servislerinin performansı",
        ],
        "expected_type": QuestionType.COMPARISON,
    },
]


# ============================================================================
# TEST FONKSİYONLARI
# ============================================================================

def test_single_question(router: AdvancedIntentRouter, question: str, verbose: bool = False):
    """Tek bir soruyu test eder"""
    result = router.analyze_question(question)
    
    if verbose:
        print("\n" + router.explain_analysis(result))
    else:
        print(f"\nSoru: {question}")
        print(f"Intent: {result.primary_question.question_type.value} (skor: {result.primary_score:.2f})")
        print(f"Dimensions: {result.suggested_plan.group_by if result.suggested_plan else []}")
        print(f"Metrics: {result.suggested_plan.metrics if result.suggested_plan else []}")
        if result.entities.vehicle_ids:
            print(f"Araç ID: {result.entities.vehicle_ids}")
        if result.entities.years:
            print(f"Yıl: {result.entities.years}")
        if result.entities.months:
            print(f"Ay: {result.entities.months}")
    
    return result


def test_category(router: AdvancedIntentRouter, category_data: dict):
    """Bir kategoriyi test eder"""
    print("\n" + "=" * 70)
    print(f"KATEGORİ: {category_data['category']}")
    print("=" * 70)
    
    correct = 0
    total = len(category_data['questions'])
    expected = category_data['expected_type']
    
    for question in category_data['questions']:
        result = router.analyze_question(question)
        is_correct = result.primary_question.question_type == expected
        
        status = "✓" if is_correct else "✗"
        print(f"{status} {question}")
        print(f"  → {result.primary_question.question_type.value} (skor: {result.primary_score:.2f})")
        
        if is_correct:
            correct += 1
    
    accuracy = (correct / total) * 100
    print(f"\nDoğruluk: {correct}/{total} ({accuracy:.1f}%)")
    
    return accuracy


def test_all_categories(router: AdvancedIntentRouter):
    """Tüm kategorileri test eder"""
    print("\n" + "=" * 70)
    print("TÜM KATEGORİLER İÇİN TEST")
    print("=" * 70)
    
    total_questions = 0
    total_correct = 0
    category_results = []
    
    for category_data in TEST_QUESTIONS:
        accuracy = test_category(router, category_data)
        category_results.append({
            "category": category_data['category'],
            "accuracy": accuracy,
            "count": len(category_data['questions']),
        })
        
        questions_count = len(category_data['questions'])
        correct_count = int((accuracy / 100) * questions_count)
        total_questions += questions_count
        total_correct += correct_count
    
    # Genel özet
    print("\n" + "=" * 70)
    print("GENEL ÖZET")
    print("=" * 70)
    
    for result in category_results:
        print(f"{result['category']:25s}: {result['accuracy']:5.1f}% ({result['count']} soru)")
    
    overall_accuracy = (total_correct / total_questions) * 100
    print(f"\n{'TOPLAM':25s}: {overall_accuracy:5.1f}% ({total_questions} soru)")
    
    return overall_accuracy


def demo_workflow():
    """Sistemin çalışma akışını gösterir"""
    print("\n" + "=" * 70)
    print("WORKFLOW DEMOSTRASYONu")
    print("=" * 70)
    
    router = AdvancedIntentRouter()
    
    # Örnek 1: Basit malzeme sorusu
    print("\n" + "-" * 70)
    print("ÖRNEK 1: Basit Malzeme Sorusu")
    print("-" * 70)
    
    question = "2023 yılında en çok kullanılan malzemeler neler?"
    result = test_single_question(router, question, verbose=True)
    
    # Örnek 2: Araç geçmişi
    print("\n" + "-" * 70)
    print("ÖRNEK 2: Araç Bakım Geçmişi")
    print("-" * 70)
    
    question = "70886 plakalı aracın bakım geçmişini göster"
    result = test_single_question(router, question, verbose=True)
    
    # Örnek 3: Karmaşık arıza sorusu
    print("\n" + "-" * 70)
    print("ÖRNEK 3: Karmaşık Arıza Sorusu")
    print("-" * 70)
    
    question = "MAN otobüslerde 2022 kış aylarında hangi arızalar görüldü?"
    result = test_single_question(router, question, verbose=True)
    
    # Örnek 4: Karşılaştırma
    print("\n" + "-" * 70)
    print("ÖRNEK 4: Karşılaştırma Sorusu")
    print("-" * 70)
    
    question = "MAN ve Mercedes otobüslerinin bakım maliyetlerini karşılaştır"
    result = test_single_question(router, question, verbose=True)


def test_schema():
    """xAPI Schema'yı test eder"""
    print("\n" + "=" * 70)
    print("SCHEMA TEST")
    print("=" * 70)
    
    # Geçerli bir statement
    valid_statement = {
        "id": "49cbf971-40f8-4341-9e46-787e3180fa44",
        "actor": {
            "name": "Arac 70886",
            "objectType": "Agent",
            "account": {
                "name": "vehicle/70886",
                "homePage": "https://promptever.com"
            }
        },
        "verb": {
            "id": "https://promptever.com/verbs/maintained",
            "display": {
                "tr-TR": "Bakım",
                "en-US": "Maintained"
            }
        },
        "object": {
            "id": "https://promptever.com/activities/material/ZU.FUCHS-SE55",
            "definition": {
                "name": {
                    "tr-TR": "fuchs reniso triton se 55 1lt",
                    "en-US": "fuchs reniso triton se 55 1lt"
                },
                "type": "https://promptever.com/activitytypes/material"
            },
            "objectType": "Activity"
        },
        "result": {
            "extensions": {
                "https://promptever.com/extensions/odometerReading": 278796,
                "https://promptever.com/extensions/faultCode": "wd1a2000000zw",
                "https://promptever.com/extensions/materialCost": 260.43,
                "https://promptever.com/extensions/materialQuantity": 3
            },
            "success": True,
            "completion": True
        },
        "context": {
            "extensions": {
                "https://promptever.com/extensions/vehicleType": "bus",
                "https://promptever.com/extensions/manufacturer": "man",
                "https://promptever.com/extensions/operationDate": "2017-11-24T00:00:00.000Z",
            }
        },
        "timestamp": "2017-07-05T15:25:11.000Z",
    }
    
    print("\nGeçerli statement testi:")
    errors = validate_statement(valid_statement)
    if errors:
        print("  ✗ Hatalar bulundu:")
        for error in errors:
            print(f"    - {error}")
    else:
        print("  ✓ Statement geçerli!")
    
    # Entity extraction testi
    print("\nEntity extraction testi:")
    extractors = XAPI_STATEMENT_SCHEMA['extractors']
    
    vehicle_id = extractors['vehicle_id'](valid_statement)
    print(f"  Vehicle ID: {vehicle_id}")
    
    material_id = extractors['material_id'](valid_statement)
    print(f"  Material ID: {material_id}")
    
    # Schema bilgileri
    print("\nSchema İstatistikleri:")
    dims = XAPI_STATEMENT_SCHEMA['dimensions']
    metrics = XAPI_STATEMENT_SCHEMA['metrics']
    print(f"  Toplam Dimension: {len(dims)}")
    print(f"  Toplam Metric: {len(metrics)}")
    
    print("\nQueryable Dimensions:")
    queryable = [k for k, v in dims.items() if v.get('queryable', False)]
    for dim in queryable[:10]:  # İlk 10'u göster
        print(f"  - {dim}: {dims[dim]['display_name']}")


def interactive_mode():
    """Kullanıcının kendi sorularını test etmesini sağlar"""
    print("\n" + "=" * 70)
    print("İNTERAKTİF MOD")
    print("=" * 70)
    print("Kendi sorularınızı test edebilirsiniz.")
    print("Çıkmak için 'q' yazın.\n")
    
    router = AdvancedIntentRouter()
    
    while True:
        question = input("\nSorunuz: ").strip()
        
        if not question or question.lower() == 'q':
            print("İnteraktif mod sonlandırılıyor...")
            break
        
        try:
            result = test_single_question(router, question, verbose=True)
        except Exception as e:
            print(f"Hata oluştu: {e}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Ana test fonksiyonu"""
    import sys
    
    # Argüman kontrolü
    mode = sys.argv[1] if len(sys.argv) > 1 else "demo"
    
    if mode == "test":
        # Tüm testleri çalıştır
        router = AdvancedIntentRouter()
        overall_accuracy = test_all_categories(router)
        print(f"\n{'='*70}")
        print(f"Sistem Genel Başarı Oranı: {overall_accuracy:.1f}%")
        print(f"{'='*70}\n")
    
    elif mode == "demo":
        # Workflow demonstrasyonu
        demo_workflow()
    
    elif mode == "schema":
        # Schema testi
        test_schema()
    
    elif mode == "interactive":
        # İnteraktif mod
        interactive_mode()
    
    elif mode == "single":
        # Tek bir soru test et
        if len(sys.argv) < 3:
            print("Kullanım: python test_question_analysis.py single 'sorunuz'")
            return
        
        question = sys.argv[2]
        router = AdvancedIntentRouter()
        test_single_question(router, question, verbose=True)
    
    else:
        print("Geçersiz mod. Kullanım:")
        print("  python test_question_analysis.py test         # Tüm testleri çalıştır")
        print("  python test_question_analysis.py demo         # Workflow göster")
        print("  python test_question_analysis.py schema       # Schema test et")
        print("  python test_question_analysis.py interactive  # İnteraktif mod")
        print("  python test_question_analysis.py single 'soru'# Tek soru test et")


if __name__ == "__main__":
    main()
