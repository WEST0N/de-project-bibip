import os
from typing import List, Optional, Tuple
from collections import defaultdict
from decimal import Decimal
from datetime import datetime


from models import Car, CarFullInfo, CarStatus, Model, ModelSaleStats, Sale



class CarService:
    RECORD_SIZE = 500
    RECORD_SIZE_WITH_NL = 501
    
    def __init__(self, root_directory_path: str) -> None:
        self.root_directory_path = root_directory_path
        os.makedirs(root_directory_path, exist_ok=True)
        
        # Модели
        self.models_file = os.path.join(root_directory_path, 'models.txt')
        self.models_index_file = os.path.join(root_directory_path, 'models_index.txt')
        
        # Автомобили
        self.cars_file = os.path.join(root_directory_path, 'cars.txt')
        self.cars_index_file = os.path.join(root_directory_path, 'cars_index.txt')
        
        # Продажи
        self.sales_file = os.path.join(root_directory_path, 'sales.txt')
        self.sales_index_file = os.path.join(root_directory_path, 'sales_index.txt')
        
        self._init_files() # Это метод, который создаёт пустые файлы, если их нет.


    def _init_files(self):
        for file_path in [self.models_file, self.models_index_file, # Просто проверяет наличие всех 6 файлов.
                         self.cars_file, self.cars_index_file,
                         self.sales_file, self.sales_index_file]:
            if not os.path.exists(file_path):
                with open(file_path, 'w') as f:
                    pass
        

    def _format_record(self, data: str) -> str: # Выравнивает запись (data) до 500 символов, заполняя пробелами справа.
        return data.ljust(self.RECORD_SIZE) + '\n'


    # Считывает индексный файл строками, каждая строка имеет формат "ключ:позиция"
    def _load_index(self, index_file: str) -> List[Tuple[str, int]]: 
        if not os.path.exists(index_file):
            return []
        with open(index_file, 'r') as f:
            lines = f.readlines()
        index = []
        for line in lines:
            if ':' in line:
                key, pos_str = line.strip().split(':', 1)
                index.append((key, int(pos_str)))
        return sorted(index, key=lambda x: x[0])

    # Сохранение индекса
    def _save_index(self, index: List[Tuple[str, int]], index_file: str):
        with open(index_file, 'w') as f:
            for key, pos in index:
                f.write(f"{key}:{pos}\n")

    # Запись данных
    def _write_record(self, file_path: str, position: int, record: str):
        with open(file_path, 'r+') as f:
            f.seek(position * self.RECORD_SIZE_WITH_NL) 
            f.write(record)

    # Чтение данных
    def _read_record(self, file_path: str, position: int) -> str: 
        with open(file_path, 'r') as f:
            f.seek(position * self.RECORD_SIZE_WITH_NL)
            return f.read(self.RECORD_SIZE).rstrip()

    # Поиск свободной позиции
    def _find_free_position(self, data_file: str) -> int:
        size = os.path.getsize(data_file)
        return size // self.RECORD_SIZE_WITH_NL

    # Сохранение автомобилей и моделей
    def add_model(self, model: Model) -> Model:
        model_data = f"{model.id}|{model.name}|{model.brand}"
        formatted = self._format_record(model_data)
        position = self._find_free_position(self.models_file)
        self._write_record(self.models_file, position, formatted)
        
        index = self._load_index(self.models_index_file)
        index.append((str(model.id), position))
        index.sort(key=lambda x: x[0])
        self._save_index(index, self.models_index_file)
        return model


    def add_car(self, car: Car) -> Car:
        car_data = f"{car.vin}|{car.model}|{car.price}|{car.date_start.isoformat()}|{car.status.value}"
        formatted = self._format_record(car_data)
        position = self._find_free_position(self.cars_file)
        self._write_record(self.cars_file, position, formatted)
        
        index = self._load_index(self.cars_index_file)
        index.append((car.vin, position))
        index.sort(key=lambda x: x[0])
        self._save_index(index, self.cars_index_file)
        return car

    #  Сохранение продаж
    def sell_car(self, sale: Sale) -> Car:
        sale_data = f"{sale.sales_number}|{sale.car_vin}|{sale.cost}|{sale.sales_date.isoformat()}|False"
        formatted = self._format_record(sale_data)
        position = self._find_free_position(self.sales_file)
        self._write_record(self.sales_file, position, formatted)
        
        index = self._load_index(self.sales_index_file)
        index.append((sale.sales_number, position))
        index.sort(key=lambda x: x[0])
        self._save_index(index, self.sales_index_file)
        
        self._update_car_status(sale.car_vin, CarStatus.sold.value)
        return self._get_car_by_vin(sale.car_vin)

    # Чтение списка машин
    def get_cars(self, status: CarStatus) -> List[Car]:
        cars = []
        file_size = os.path.getsize(self.cars_file)
        if file_size == 0:
            return []
        total_records = file_size // self.RECORD_SIZE_WITH_NL
        for pos in range(total_records):
            record = self._read_record(self.cars_file, pos)
            if record.strip():  
                fields = record.split('|', 4)
                if len(fields) == 5 and fields[4].strip() == status.value:
                    cars.append(Car.model_validate({
                        'vin': fields[0].strip(),
                        'model': fields[1].strip(),
                        'price': fields[2].strip(),
                        'date_start': fields[3].strip(),
                        'status': fields[4].strip()
                    }))
        return cars  

    # Вывод детальной информации
    def get_car_info(self, vin: str) -> Optional[CarFullInfo]:
        car_data = self._find_car_by_vin(vin)
        if not car_data:
            return None
        
        fields = car_data.split('|', 4)
        if len(fields) != 5:
            return None
        
        car_vin, model_id, price_str, date_str, status_str = [f.strip() for f in fields]
        
        model_data = self._find_model_by_id(model_id)
        if not model_data:
            return None
        
        m_fields = model_data.split('|', 2)
        if len(m_fields) != 3:
            return None
        
        _, model_name, brand = [f.strip() for f in m_fields]
        
        sales_date = sales_cost = None
        if status_str == CarStatus.sold.value:
            sale_data = self._find_active_sale_by_vin(car_vin)
            if sale_data:
                s_fields = sale_data.split('|', 4)
                if len(s_fields) == 5:
                    _, _, cost_str, date_s_str, _ = [f.strip() for f in s_fields]
                    sales_date = datetime.fromisoformat(date_s_str)
                    sales_cost = Decimal(cost_str)
        
        return CarFullInfo.model_validate({
            'vin': car_vin,
            'car_model_name': model_name,
            'car_model_brand': brand,
            'price': price_str,
            'date_start': date_str,
            'status': status_str,
            'sales_date': sales_date,
            'sales_cost': sales_cost
        })

    # Обновление ключевого поля
    def update_vin(self, vin: str, new_vin: str) -> Car:
        cars_index = self._load_index(self.cars_index_file)
        position = None
        index_entry = None
        
        for i, (idx_vin, pos) in enumerate(cars_index):
            if idx_vin == vin:
                position = pos
                index_entry = i
                break
        
        if position is None:
            raise ValueError(f"Car {vin} not found")
        
        record = self._read_record(self.cars_file, position)
        fields = record.split('|', 4)
        if len(fields) == 5:
            fields[0] = new_vin
            self._write_record(self.cars_file, position, self._format_record('|'.join(fields)))
        
        cars_index[index_entry] = (new_vin, position)
        cars_index.sort(key=lambda x: x[0])
        self._save_index(cars_index, self.cars_index_file)
        
        return self._get_car_by_vin(new_vin)

    # Удаление продажи (отмена)
    def revert_sale(self, sales_number: str) -> Car:
        sales_index = self._load_index(self.sales_index_file)
        position = None
        
        for idx_sales, pos in sales_index:
            if idx_sales == sales_number:
                position = pos
                break
        
        if position is None:
            raise ValueError(f"Sale {sales_number} not found")
        
        record = self._read_record(self.sales_file, position)
        fields = record.split('|', 4)
        if len(fields) != 5:
            raise ValueError("Invalid sale format")
        
        if fields[4].strip() == 'True':
            raise ValueError(f"Sale {sales_number} already deleted")
        
        fields[4] = 'True'
        self._write_record(self.sales_file, position, self._format_record('|'.join(fields)))
        
        car_vin = fields[1].strip()
        self._update_car_status(car_vin, CarStatus.available.value)
        return self._get_car_by_vin(car_vin)

    # Самые продаваемые модели
    def top_models_by_sales(self) -> List[ModelSaleStats]:
        model_sales = defaultdict(int)
        
        
        file_size = os.path.getsize(self.sales_file)
        if file_size == 0:
            return []
        
        total_records = file_size // self.RECORD_SIZE_WITH_NL
        for pos in range(total_records):
            record = self._read_record(self.sales_file, pos)
            if not record.strip():  
                continue
            fields = record.split('|', 4)
            if len(fields) == 5 and fields[4].strip() == 'False':  
                car_vin = fields[1].strip()
                car_data = self._find_car_by_vin(car_vin)
                if car_data:
                    c_fields = car_data.split('|', 4)
                    if len(c_fields) == 5:
                        model_id = c_fields[1].strip()  
                        model_sales[model_id] += 1
                
        models_index = self._load_index(self.models_index_file)
        models_data = {}
        for model_id, pos in models_index:
            model_record = self._read_record(self.models_file, pos)
            if model_record.strip():
                m_fields = model_record.split('|', 2)
                if len(m_fields) == 3:
                    name = m_fields[1].strip()
                    brand = m_fields[2].strip()
                    models_data[model_id] = (name, brand)
        
        sorted_models = sorted(model_sales.items(), key=lambda x: x[1], reverse=True)[:3]
        result = []
        for model_id, sales_count in sorted_models:
            if model_id in models_data:
                name, brand = models_data[model_id]
                result.append(ModelSaleStats(
                    car_model_name=name,
                    brand=brand,
                    sales_number=sales_count
                ))
        
        return result




    # Вспомогательные методы
    def _find_car_by_vin(self, vin: str) -> Optional[str]: # Линейный поиск по индексу
        for v, pos in self._load_index(self.cars_index_file):
            if v == vin:
                return self._read_record(self.cars_file, pos)
        return None


    def _find_model_by_id(self, model_id: str) -> Optional[str]:
        for m, pos in self._load_index(self.models_index_file):
            if m == model_id:
                return self._read_record(self.models_file, pos)
        return None


    def _find_active_sale_by_vin(self, vin: str) -> Optional[str]:
        file_size = os.path.getsize(self.sales_file)
        if file_size == 0:
            return None
        total = file_size // self.RECORD_SIZE_WITH_NL
        for pos in range(total):
            record = self._read_record(self.sales_file, pos)
            fields = record.split('|', 4)
            if len(fields) == 5 and fields[1].strip() == vin and fields[4].strip() == 'False':
                return record
        return None


    def _get_car_by_vin(self, vin: str) -> Car:
        data = self._find_car_by_vin(vin)
        if not data:
            raise ValueError(f"Car {vin} not found")
        fields = data.split('|', 4)
        return Car.model_validate({
            'vin': fields[0].strip(),
            'model': fields[1].strip(),
            'price': fields[2].strip(),
            'date_start': fields[3].strip(),
            'status': fields[4].strip()
        })


    def _update_car_status(self, vin: str, status: str):
        cars_index = self._load_index(self.cars_index_file)
        for v, pos in cars_index:
            if v == vin:
                record = self._read_record(self.cars_file, pos)
                fields = record.split('|', 4)
                if len(fields) == 5:
                    fields[4] = status
                    self._write_record(self.cars_file, pos, self._format_record('|'.join(fields)))
                return
